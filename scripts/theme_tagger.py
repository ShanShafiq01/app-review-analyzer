"""
Theme tagger.

Classifies reviews into thematic buckets using keyword matching against
a theme taxonomy JSON. Supports taxonomy inheritance (e.g. health_wellness
extends general).

For higher accuracy, use llm_tagger.py instead (requires an API key).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def load_taxonomy(taxonomy_path: str | Path, themes_dir: str | Path = None) -> dict:
    """
    Load a theme taxonomy JSON, resolving 'extends' inheritance.

    Args:
        taxonomy_path: Path to the taxonomy JSON file (or just its name like "general")
        themes_dir: Directory containing taxonomy files (defaults to ../templates/themes/)

    Returns:
        Resolved taxonomy dict with all themes merged
    """
    if themes_dir is None:
        themes_dir = Path(__file__).parent.parent / "templates" / "themes"
    else:
        themes_dir = Path(themes_dir)

    # Accept both names ("general") and paths
    p = Path(taxonomy_path)
    if not p.exists():
        candidate = themes_dir / f"{taxonomy_path}.json"
        if candidate.exists():
            p = candidate
        else:
            raise FileNotFoundError(f"Taxonomy not found: {taxonomy_path}")

    taxonomy = json.loads(p.read_text())

    # Resolve inheritance chain
    if taxonomy.get("extends"):
        parent_name = taxonomy["extends"]
        parent = load_taxonomy(parent_name, themes_dir=themes_dir)
        # Merge: parent themes first, child themes override / add
        merged_neg = dict(parent.get("negative_themes", {}))
        merged_neg.update(taxonomy.get("negative_themes", {}))
        merged_pos = dict(parent.get("positive_themes", {}))
        merged_pos.update(taxonomy.get("positive_themes", {}))
        taxonomy["negative_themes"] = merged_neg
        taxonomy["positive_themes"] = merged_pos

    return taxonomy


def detect_non_english(text: str) -> bool:
    """
    Simple heuristic to detect non-English reviews.
    Counts the share of ASCII letters; <60% likely means non-Latin script.
    Doesn't catch all cases but works for the most common ones.
    """
    if not text or len(text) < 10:
        return False
    ascii_letters = sum(1 for c in text if c.isalpha() and c.isascii())
    letters = sum(1 for c in text if c.isalpha())
    if letters == 0:
        return False
    return ascii_letters / letters < 0.6


def tag_review(text: str, themes: dict) -> list[str]:
    """
    Tag a single review against a set of themes.

    Args:
        text: The review body
        themes: Dict of {theme_key: {"keywords": [...], ...}}

    Returns:
        List of theme keys that match
    """
    if not isinstance(text, str) or not text.strip():
        return []
    lower = text.lower()
    matches = []
    for key, theme_def in themes.items():
        for kw in theme_def.get("keywords", []):
            if kw.lower() in lower:
                matches.append(key)
                break
    return matches


def tag_reviews(reviews: list[dict], taxonomy: dict) -> list[dict]:
    """
    Tag a list of reviews against a taxonomy. Negative themes apply to
    1-3 star reviews; positive themes apply to 4-5 star reviews.

    Returns:
        Enriched reviews with 'themes_neg', 'themes_pos', 'is_non_english' fields.
    """
    neg_themes = taxonomy.get("negative_themes", {})
    pos_themes = taxonomy.get("positive_themes", {})

    out = []
    for r in reviews:
        review = dict(r)
        text = review.get("review", "") or ""
        rating = int(review.get("rating", 0) or 0)

        # Skip non-English for thematic analysis but keep in data
        is_non_english = detect_non_english(text)
        review["is_non_english"] = is_non_english

        if is_non_english:
            review["themes_neg"] = []
            review["themes_pos"] = []
        else:
            # Tag against the appropriate polarity buckets
            review["themes_neg"] = tag_review(text, neg_themes) if rating <= 3 else []
            review["themes_pos"] = tag_review(text, pos_themes) if rating >= 4 else []

        out.append(review)
    return out


def list_available_taxonomies(themes_dir: str | Path = None) -> list[dict]:
    """List all taxonomies available in the themes directory."""
    if themes_dir is None:
        themes_dir = Path(__file__).parent.parent / "templates" / "themes"
    else:
        themes_dir = Path(themes_dir)
    out = []
    for p in sorted(themes_dir.glob("*.json")):
        try:
            data = json.loads(p.read_text())
            out.append({
                "name": data.get("name", p.stem),
                "label": data.get("label", p.stem),
                "description": data.get("description", ""),
                "path": str(p),
            })
        except Exception:
            continue
    return out


def suggest_taxonomy(app_category: str) -> str:
    """
    Suggest a taxonomy name based on the app store category.
    Falls back to 'general' if no match.
    """
    if not app_category:
        return "general"
    c = app_category.lower()
    mapping = {
        "health & fitness": "health_wellness",
        "medical": "health_wellness",
        "lifestyle": "health_wellness",  # often health/wellness adjacent
        "finance": "fintech",
        "banking": "fintech",
        "shopping": "ecommerce",
        "food & drink": "ecommerce",
        "social networking": "social",
        "communication": "social",
        "dating": "social",
        "productivity": "productivity",
        "business": "productivity",
        "utilities": "productivity",
        "games": "gaming",
        "game": "gaming",
        "puzzle": "gaming",
        "rpg": "gaming",
        "strategy": "gaming",
    }
    for key, taxonomy in mapping.items():
        if key in c:
            return taxonomy
    return "general"
