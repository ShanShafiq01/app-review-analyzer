"""
App Store review scraper — production-hardened.

Pulls reviews via Apple's public RSS feed with:
  - Exponential backoff with jitter on 429/503
  - Country rotation (instead of hammering one country)
  - Honors Retry-After headers
  - Country-less RSS feed as a last-resort fallback
  - Graceful degradation: returns what it got even when Apple blocks fully
  - User-friendly progress messages, not raw HTTP codes
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

try:
    from _http import FetchSession, RateLimitedError
except ImportError:
    from scripts._http import FetchSession, RateLimitedError


DEFAULT_COUNTRIES = ["us", "gb", "ca", "au", "nz", "ie"]
RSS_URL = "https://itunes.apple.com/{country}/rss/customerreviews/page={page}/id={app_id}/sortby=mostrecent/json"
RSS_FALLBACK_URL = "https://itunes.apple.com/rss/customerreviews/page={page}/id={app_id}/sortby=mostrecent/json"
LOOKUP_URL = "https://itunes.apple.com/lookup?id={app_id}&country={country}"


def fetch_appstore_reviews(
    app_id: int | str,
    countries: Iterable[str] = None,
    max_pages_per_country: int = 10,
    progress_callback=None,
) -> dict:
    """
    Returns dict with reviews, partial flag, blocked countries, and a user-friendly warning.
    Never raises for rate limits — degrades gracefully.
    """
    if countries is None:
        countries = DEFAULT_COUNTRIES
    countries = list(countries)

    session = FetchSession(progress_callback=progress_callback)
    session._log(f"Fetching App Store reviews for app ID {app_id}...")

    seen_ids = set()
    all_reviews = []
    countries_succeeded = []
    countries_blocked = []
    countries_attempted = []
    total_pages = 0

    # Country rotation: interleave pages across countries
    task_queue = []
    for page in range(1, max_pages_per_country + 1):
        for country in countries:
            task_queue.append((country, page))

    country_done = {c: False for c in countries}
    country_failed = {c: False for c in countries}

    for country, page in task_queue:
        if country_done.get(country) or country_failed.get(country):
            continue
        if session.should_give_up(threshold=4):
            session._log(f"  Apple is heavily rate-limiting right now. Stopping to preserve what we have.")
            for c in countries:
                if c not in countries_succeeded and c not in countries_blocked:
                    countries_blocked.append(c)
            break
        if country not in countries_attempted:
            countries_attempted.append(country)

        url = RSS_URL.format(country=country, page=page, app_id=app_id)
        try:
            data = session.fetch_json(url)
        except RateLimitedError:
            session._log(f"  {country.upper()}: rate-limited after retries — skipping remaining pages")
            country_failed[country] = True
            if country not in countries_blocked:
                countries_blocked.append(country)
            continue

        if data is None:
            country_done[country] = True
            continue

        entries = data.get("feed", {}).get("entry", [])
        reviews = [e for e in entries if isinstance(e, dict) and "im:rating" in e]
        if not reviews:
            country_done[country] = True
            continue

        added = 0
        for entry in reviews:
            rid = entry.get("id", {}).get("label")
            if not rid or rid in seen_ids:
                continue
            seen_ids.add(rid)
            all_reviews.append(_normalize_entry(entry, country))
            added += 1
        if added:
            total_pages += 1
            if country not in countries_succeeded:
                countries_succeeded.append(country)
        session.polite_pause(0.3)

    # Fallback: country-less RSS as a last resort
    if not all_reviews and not session.should_give_up(threshold=10):
        session._log("  Trying country-less RSS feed as fallback...")
        for page in range(1, max_pages_per_country + 1):
            url = RSS_FALLBACK_URL.format(page=page, app_id=app_id)
            try:
                data = session.fetch_json(url)
            except RateLimitedError:
                break
            if data is None:
                break
            entries = data.get("feed", {}).get("entry", [])
            reviews = [e for e in entries if isinstance(e, dict) and "im:rating" in e]
            if not reviews:
                break
            for entry in reviews:
                rid = entry.get("id", {}).get("label")
                if rid and rid not in seen_ids:
                    seen_ids.add(rid)
                    all_reviews.append(_normalize_entry(entry, "us"))
            total_pages += 1
            session.polite_pause(0.3)

    partial = len(countries_blocked) > 0 or (not all_reviews and countries_attempted)
    warning = None
    if partial and all_reviews:
        warning = (
            f"Partial App Store data: {len(countries_blocked)} of {len(countries_attempted)} "
            f"countries were rate-limited by Apple. Got {len(all_reviews)} reviews from "
            f"{len(countries_succeeded)} countries. Try again in 30 minutes for full coverage."
        )
    elif not all_reviews:
        warning = (
            "Apple's RSS feed returned no reviews. Either the app isn't on the App Store, "
            "or Apple is rate-limiting all requests right now. If you have Play Store data, "
            "the pipeline will continue with Play-only. Otherwise try again in 30 minutes."
        )

    if all_reviews:
        session._log(
            f"  Got {len(all_reviews)} App Store reviews from {len(countries_succeeded)} countries"
            f"{f' ({len(countries_blocked)} blocked)' if countries_blocked else ''}"
        )

    return {
        "reviews": all_reviews,
        "partial": partial,
        "countries_attempted": countries_attempted,
        "countries_succeeded": countries_succeeded,
        "countries_blocked": countries_blocked,
        "total_pages_fetched": total_pages,
        "warning_message": warning,
    }


def _normalize_entry(entry, country):
    def get(d, *keys, default=""):
        cur = d
        for k in keys:
            if not isinstance(cur, dict):
                return default
            cur = cur.get(k)
        return cur if cur is not None else default

    try:
        rating = int(get(entry, "im:rating", "label", default="0") or 0)
    except (TypeError, ValueError):
        rating = 0

    return {
        "review_id": get(entry, "id", "label"),
        "user": get(entry, "author", "name", "label") or "Anonymous",
        "rating": rating,
        "title": get(entry, "title", "label"),
        "review": get(entry, "content", "label"),
        "date": (get(entry, "updated", "label") or "")[:10],
        "date_full": get(entry, "updated", "label"),
        "app_version": get(entry, "im:version", "label"),
        "vote_sum": _safe_int(get(entry, "im:voteSum", "label")),
        "vote_count": _safe_int(get(entry, "im:voteCount", "label")),
        "country_code": country,
        "language": "en",
    }


def _safe_int(val):
    try:
        return int(val) if val else 0
    except (TypeError, ValueError):
        return 0


def fetch_app_metadata(app_id, country="us", progress_callback=None):
    session = FetchSession(progress_callback=progress_callback)
    url = LOOKUP_URL.format(app_id=app_id, country=country)
    try:
        data = session.fetch_json(url, retries=2)
    except RateLimitedError:
        return {"error": "Could not fetch app metadata (rate-limited)"}
    if not data:
        return {"error": "App not found at that ID"}
    results = data.get("results", [])
    if not results:
        return {"error": "App not found at that ID"}
    r = results[0]
    return {
        "title": r.get("trackName"),
        "developer": r.get("artistName"),
        "score": r.get("averageUserRating"),
        "ratings_count": r.get("userRatingCount"),
        "version": r.get("version"),
        "category": r.get("primaryGenreName"),
        "price": r.get("price"),
        "currency": r.get("currency"),
        "description": (r.get("description") or "")[:500],
        "bundle_id": r.get("bundleId"),
    }


def main():
    parser = argparse.ArgumentParser(description="Scrape App Store reviews via RSS feed")
    parser.add_argument("--app-id", required=True)
    parser.add_argument("--output", default="-")
    parser.add_argument("--countries", default="us,gb,ca,au")
    parser.add_argument("--metadata-only", action="store_true")
    args = parser.parse_args()

    if args.metadata_only:
        out = json.dumps(fetch_app_metadata(args.app_id), indent=2)
    else:
        countries = [c.strip() for c in args.countries.split(",")]
        result = fetch_appstore_reviews(args.app_id, countries=countries)
        out = json.dumps(result, indent=2)

    if args.output == "-":
        print(out)
    else:
        Path(args.output).write_text(out)


if __name__ == "__main__":
    main()
