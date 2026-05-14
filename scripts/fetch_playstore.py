"""
Play Store review scraper — production-hardened.

google-play-scraper is fairly robust on its own (less aggressive rate-limiting
than Apple), but we wrap it with:
  - User-friendly progress messages
  - Per-locale failure isolation (one locale failing doesn't kill the whole run)
  - Returns a result dict consistent with fetch_appstore.fetch_appstore_reviews
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Iterable

try:
    from google_play_scraper import reviews_all, Sort, app as app_info
except ImportError:
    print("ERROR: google-play-scraper not installed. Run: pip install google-play-scraper", file=sys.stderr)
    sys.exit(1)


DEFAULT_LOCALES = [("us", "en"), ("gb", "en"), ("ca", "en"), ("au", "en")]


def fetch_playstore_reviews(
    app_id: str,
    locales: Iterable[tuple[str, str]] = None,
    sorts: list = None,
    progress_callback=None,
) -> dict:
    """
    Fetch all available Play Store reviews. Returns a result dict matching
    the App Store scraper's shape.
    """
    def _log(msg):
        if progress_callback:
            progress_callback(msg)
        else:
            print(msg, file=sys.stderr)

    if locales is None:
        locales = DEFAULT_LOCALES
    if sorts is None:
        sorts = [Sort.NEWEST, Sort.MOST_RELEVANT, Sort.RATING]

    _log(f"Fetching Google Play reviews for {app_id}...")

    all_reviews = {}
    locales_succeeded = []
    locales_blocked = []
    locales_attempted = []

    for country, lang in locales:
        loc_key = f"{country}/{lang}"
        locales_attempted.append(loc_key)
        before = len(all_reviews)
        loc_succeeded = False

        for sort_order in sorts:
            try:
                result = reviews_all(app_id, lang=lang, country=country, sort=sort_order)
                for r in result:
                    rid = r.get("reviewId")
                    if rid and rid not in all_reviews:
                        r["_source_country"] = country
                        r["_source_lang"] = lang
                        all_reviews[rid] = r
                loc_succeeded = True
                time.sleep(0.2)  # polite
            except Exception as exc:
                # google-play-scraper raises various errors — log and continue
                _log(f"  {loc_key} sort={sort_order.name}: {type(exc).__name__} (continuing)")
                continue

        added = len(all_reviews) - before
        if loc_succeeded and added > 0:
            locales_succeeded.append(loc_key)
            _log(f"  {loc_key}: +{added} new reviews (total: {len(all_reviews)})")
        elif not loc_succeeded:
            locales_blocked.append(loc_key)

    # Normalize to canonical shape
    normalized = []
    for r in all_reviews.values():
        normalized.append({
            "review_id": r.get("reviewId"),
            "user": r.get("userName") or "Anonymous",
            "rating": int(r.get("score", 0) or 0),
            "date": str(r.get("at", ""))[:10] if r.get("at") else "",
            "date_full": str(r.get("at", "")),
            "review": r.get("content") or "",
            "helpful_count": int(r.get("thumbsUpCount", 0) or 0),
            "app_version": r.get("reviewCreatedVersion") or "",
            "developer_reply": r.get("replyContent") or "",
            "reply_date": str(r.get("repliedAt", "")) if r.get("repliedAt") else "",
            "country_code": r.get("_source_country", "us"),
            "language": r.get("_source_lang", "en"),
        })

    partial = bool(locales_blocked)
    warning = None
    if partial and normalized:
        warning = (
            f"Partial Play Store data: {len(locales_blocked)} of {len(locales_attempted)} "
            f"locales failed. Got {len(normalized)} reviews from {len(locales_succeeded)} locales."
        )
    elif not normalized:
        warning = (
            "Play Store returned no reviews. Either the app ID is wrong, the app has no published "
            "reviews, or Google is rate-limiting. Verify the package name and try again."
        )

    if normalized:
        _log(f"  Got {len(normalized)} Play Store reviews total")

    return {
        "reviews": normalized,
        "partial": partial,
        "countries_attempted": [l.split("/")[0] for l in locales_attempted],
        "countries_succeeded": [l.split("/")[0] for l in locales_succeeded],
        "countries_blocked": [l.split("/")[0] for l in locales_blocked],
        "total_pages_fetched": len(locales_succeeded),
        "warning_message": warning,
    }


def fetch_app_metadata(app_id: str, progress_callback=None) -> dict:
    """Get app metadata from Play Store."""
    def _log(msg):
        if progress_callback:
            progress_callback(msg)
        else:
            print(msg, file=sys.stderr)
    try:
        info = app_info(app_id, lang="en", country="us")
        return {
            "title": info.get("title"),
            "score": info.get("score"),
            "ratings_count": info.get("ratings"),
            "reviews_count": info.get("reviews"),
            "installs": info.get("installs"),
            "real_installs": info.get("realInstalls"),
            "developer": info.get("developer"),
            "category": info.get("genre"),
            "description": (info.get("description") or "")[:500],
        }
    except Exception as exc:
        _log(f"  Couldn't fetch Play Store metadata: {exc}")
        return {"error": str(exc)}


def main():
    parser = argparse.ArgumentParser(description="Scrape Play Store reviews")
    parser.add_argument("--app-id", required=True)
    parser.add_argument("--output", default="-")
    parser.add_argument("--countries", default="us,gb,ca,au")
    parser.add_argument("--metadata-only", action="store_true")
    args = parser.parse_args()

    if args.metadata_only:
        out = json.dumps(fetch_app_metadata(args.app_id), indent=2, default=str)
    else:
        locales = [(c.strip(), "en") for c in args.countries.split(",")]
        result = fetch_playstore_reviews(args.app_id, locales=locales)
        out = json.dumps(result, indent=2, default=str)

    if args.output == "-":
        print(out)
    else:
        Path(args.output).write_text(out)


if __name__ == "__main__":
    main()
