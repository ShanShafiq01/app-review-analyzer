"""
Main analyzer.

Takes tagged reviews from each store and produces all derived analytics:
  - Rating distribution
  - Theme counts and example quotes
  - Cross-store comparison
  - Quarterly timeline
  - 4-star "Almost-Loyal" extraction
  - Power-quote candidates

Output is a single JSON dict that all the report generators consume.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict, Counter
from typing import Any


COUNTRY_NAMES = {
    "us": "United States", "gb": "United Kingdom", "ca": "Canada",
    "au": "Australia", "mx": "Mexico", "tt": "Trinidad & Tobago",
    "nz": "New Zealand", "ie": "Ireland", "in": "India",
    "za": "South Africa", "sg": "Singapore", "ph": "Philippines",
    "de": "Germany", "fr": "France", "nl": "Netherlands",
    "se": "Sweden", "es": "Spain", "br": "Brazil", "jp": "Japan",
    "no": "Norway", "dk": "Denmark", "fi": "Finland",
    "it": "Italy", "pt": "Portugal", "pl": "Poland",
    "tr": "Turkey", "ae": "United Arab Emirates", "sa": "Saudi Arabia",
    "pk": "Pakistan", "id": "Indonesia", "th": "Thailand",
    "vn": "Vietnam", "kr": "South Korea", "tw": "Taiwan",
    "hk": "Hong Kong", "ar": "Argentina", "cl": "Chile",
}


def normalize_review(review: dict, source: str) -> dict:
    """Bring a scraped review into the canonical shape used by analyses."""
    country_code = (review.get("country_code") or "us").lower()
    return {
        "source": source,
        "review_id": review.get("review_id", ""),
        "user": review.get("user") or "Anonymous",
        "rating": int(review.get("rating", 0) or 0),
        "date": review.get("date", "") or "",
        "title": review.get("title", "") or "",
        "review": (review.get("review") or "").strip(),
        "country_code": country_code,
        "country": COUNTRY_NAMES.get(country_code, country_code.upper()),
        "language": review.get("language", "en"),
        "app_version": review.get("app_version", ""),
        "helpful_count": int(review.get("helpful_count", 0) or 0),
        "vote_count": int(review.get("vote_count", 0) or 0),
        "themes_neg": review.get("themes_neg", []) or [],
        "themes_pos": review.get("themes_pos", []) or [],
        "is_non_english": bool(review.get("is_non_english", False)),
        "developer_reply": review.get("developer_reply", ""),
        "word_count": len((review.get("review") or "").split()),
    }


def aggregate_store(reviews: list[dict], source: str, taxonomy: dict) -> dict | None:
    """Compute aggregate stats and theme examples for one store."""
    src = [r for r in reviews if r["source"] == source]
    if not src:
        return None

    ratings = [r["rating"] for r in src]
    by_rating = Counter(ratings)

    neg_counts = defaultdict(int)
    pos_counts = defaultdict(int)
    neg_examples = defaultdict(list)
    pos_examples = defaultdict(list)

    for r in src:
        # Tally
        for t in r.get("themes_neg", []):
            neg_counts[t] += 1
            if len(neg_examples[t]) < 6 and 30 <= len(r["review"]) <= 600:
                neg_examples[t].append(r)
        for t in r.get("themes_pos", []):
            pos_counts[t] += 1
            if len(pos_examples[t]) < 6 and 30 <= len(r["review"]) <= 600:
                pos_examples[t].append(r)

    return {
        "source": source,
        "total": len(src),
        "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else 0,
        "by_rating": {str(k): v for k, v in by_rating.items()},
        "neg_counts": dict(neg_counts),
        "pos_counts": dict(pos_counts),
        "neg_examples": {k: v for k, v in neg_examples.items()},
        "pos_examples": {k: v for k, v in pos_examples.items()},
        "negative_total": sum(1 for r in src if r["rating"] <= 3),
        "positive_total": sum(1 for r in src if r["rating"] >= 4),
        "four_star_total": by_rating.get(4, 0),
        "one_star": by_rating.get(1, 0),
        "five_star": by_rating.get(5, 0),
        "non_english_count": sum(1 for r in src if r.get("is_non_english")),
    }


CONDITIONAL_PIVOTS = [
    "but ", "wish ", "would be ", "would love", "needs ", "if only",
    "except", "only thing", "one issue", "one complaint", "however",
    "unless", "almost 5", "almost five",
]


def find_conditional_fourstars(reviews: list[dict], source: str) -> list[dict]:
    """Extract 4-star reviews with conditional language — the 'Almost-Loyal' cohort."""
    fours = [r for r in reviews if r["source"] == source and r["rating"] == 4]
    conditional = []
    for r in fours:
        text = r["review"].lower()
        for p in CONDITIONAL_PIVOTS:
            if p in text:
                conditional.append(r)
                break
    return conditional


def build_timeline(reviews: list[dict], source: str) -> list[dict]:
    """Bucket reviews by year-month and tally rating mix per bucket."""
    by_month = defaultdict(lambda: {"neg": 0, "neu": 0, "pos": 0, "total": 0})
    for r in reviews:
        if r["source"] != source or not r["date"] or len(r["date"]) < 7:
            continue
        ym = r["date"][:7]
        bucket = by_month[ym]
        bucket["total"] += 1
        rating = r["rating"]
        if rating <= 2:
            bucket["neg"] += 1
        elif rating == 3:
            bucket["neu"] += 1
        else:
            bucket["pos"] += 1
    out = []
    for month in sorted(by_month.keys()):
        b = by_month[month]
        out.append({"month": month, **b})
    return out


def cross_store_comparison(play_agg: dict, ios_agg: dict, taxonomy: dict) -> dict:
    """Compare the two stores theme-by-theme."""
    if not play_agg or not ios_agg:
        return {}

    out = {
        "play_avg": play_agg["avg_rating"],
        "ios_avg": ios_agg["avg_rating"],
        "gap": round(ios_agg["avg_rating"] - play_agg["avg_rating"], 2),
        "play_total": play_agg["total"],
        "ios_total": ios_agg["total"],
        "play_one_star_pct": round(play_agg["one_star"] / play_agg["total"] * 100, 1) if play_agg["total"] else 0,
        "ios_one_star_pct": round(ios_agg["one_star"] / ios_agg["total"] * 100, 1) if ios_agg["total"] else 0,
        "play_five_star_pct": round(play_agg["five_star"] / play_agg["total"] * 100, 1) if play_agg["total"] else 0,
        "ios_five_star_pct": round(ios_agg["five_star"] / ios_agg["total"] * 100, 1) if ios_agg["total"] else 0,
    }

    # Theme prevalence comparison
    theme_compare = []
    play_neg = play_agg["negative_total"]
    ios_neg = ios_agg["negative_total"]
    for key, theme_def in taxonomy.get("negative_themes", {}).items():
        play_n = play_agg["neg_counts"].get(key, 0)
        ios_n = ios_agg["neg_counts"].get(key, 0)
        play_pct = play_n / play_neg * 100 if play_neg else 0
        ios_pct = ios_n / ios_neg * 100 if ios_neg else 0
        theme_compare.append({
            "key": key,
            "label": theme_def.get("label", key),
            "play_count": play_n,
            "play_pct": round(play_pct, 1),
            "ios_count": ios_n,
            "ios_pct": round(ios_pct, 1),
            "delta": round(play_pct - ios_pct, 1),
        })
    theme_compare.sort(key=lambda x: -(x["play_count"] + x["ios_count"]))
    out["themes"] = theme_compare
    return out


def find_power_quotes(reviews: list[dict], source: str, max_count: int = 5) -> list[dict]:
    """
    Pull out emotionally resonant or strategically powerful quotes.
    Heuristics:
      - 1-star reviews
      - Length between 50 and 280 characters (tweet-sized)
      - Contains strong emotional or definitive language
    """
    candidates = [
        r for r in reviews
        if r["source"] == source
        and r["rating"] == 1
        and 50 <= len(r["review"]) <= 280
        and not r.get("is_non_english")
    ]
    # Score by punchiness — short sentences, strong language
    power_words = [
        "scam", "waste", "broken", "stress", "anxious", "frustrating",
        "infuriating", "worst", "terrible", "useless", "regret",
        "money back", "deleted", "uninstall", "give up",
    ]
    def score(r):
        text = r["review"].lower()
        return sum(2 if w in text else 0 for w in power_words)

    candidates.sort(key=lambda r: -score(r))
    return candidates[:max_count]


def run_full_analysis(
    play_reviews: list[dict],
    ios_reviews: list[dict],
    taxonomy: dict,
    play_metadata: dict = None,
    ios_metadata: dict = None,
) -> dict:
    """
    Run the full analysis pipeline.

    Args:
        play_reviews: List of tagged reviews from Play Store (or empty list)
        ios_reviews: List of tagged reviews from App Store (or empty list)
        taxonomy: Loaded theme taxonomy
        play_metadata: Optional Play Store app metadata
        ios_metadata: Optional App Store app metadata

    Returns:
        Complete analysis dict for the report generators
    """
    # Normalize everything
    play_norm = [normalize_review(r, "Google Play") for r in play_reviews]
    ios_norm = [normalize_review(r, "App Store") for r in ios_reviews]
    all_reviews = play_norm + ios_norm

    # Per-store aggregates
    play_agg = aggregate_store(all_reviews, "Google Play", taxonomy)
    ios_agg = aggregate_store(all_reviews, "App Store", taxonomy)

    # 4-star conditional reviews
    play_fourstar = find_conditional_fourstars(all_reviews, "Google Play")
    ios_fourstar = find_conditional_fourstars(all_reviews, "App Store")

    # Timelines
    play_timeline = build_timeline(all_reviews, "Google Play")
    ios_timeline = build_timeline(all_reviews, "App Store")

    # Cross-store
    cross = cross_store_comparison(play_agg, ios_agg, taxonomy) if (play_agg and ios_agg) else {}

    # Power quotes
    play_power = find_power_quotes(all_reviews, "Google Play") if play_agg else []
    ios_power = find_power_quotes(all_reviews, "App Store") if ios_agg else []

    return {
        "taxonomy": {
            "name": taxonomy.get("name"),
            "label": taxonomy.get("label"),
            "negative_themes": {k: v.get("label", k) for k, v in taxonomy.get("negative_themes", {}).items()},
            "positive_themes": {k: v.get("label", k) for k, v in taxonomy.get("positive_themes", {}).items()},
        },
        "play": play_agg,
        "ios": ios_agg,
        "play_metadata": play_metadata or {},
        "ios_metadata": ios_metadata or {},
        "all_reviews": all_reviews,
        "play_fourstar": play_fourstar,
        "ios_fourstar": ios_fourstar,
        "play_timeline": play_timeline,
        "ios_timeline": ios_timeline,
        "cross": cross,
        "play_power_quotes": play_power,
        "ios_power_quotes": ios_power,
        "summary": {
            "total_reviews": len(all_reviews),
            "play_reviews": len(play_norm),
            "ios_reviews": len(ios_norm),
            "non_english_total": sum(1 for r in all_reviews if r.get("is_non_english")),
        },
    }
