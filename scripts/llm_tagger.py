"""
Optional LLM-powered theme tagger.

Uses the Anthropic API (Claude) to classify reviews into themes.
More accurate than keyword matching, but costs API credits.

Requires:
    pip install anthropic
    Environment variable ANTHROPIC_API_KEY

Cost estimate: roughly $0.10–$0.30 per app analysis depending on volume.
The default keyword tagger in theme_tagger.py is free and good enough for most cases.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any


SYSTEM_PROMPT = """You are a review classifier. Given a mobile app review, classify it against \
a list of themes. Output ONLY valid JSON. Be precise — only assign a theme if the review \
clearly expresses it. Most reviews will match 0-2 themes, occasionally 3."""


def tag_reviews_with_llm(
    reviews: list[dict],
    taxonomy: dict,
    model: str = "claude-haiku-4-5-20251001",
    batch_size: int = 10,
    verbose: bool = False,
) -> list[dict]:
    """
    Tag reviews using Claude. Falls back gracefully on errors per review.

    Args:
        reviews: List of review dicts (must have 'review' and 'rating' keys)
        taxonomy: Loaded taxonomy with negative_themes and positive_themes
        model: Anthropic model to use (Haiku is cheap and fast)
        batch_size: Reviews per API call (smaller = more accurate but more calls)
        verbose: Print progress

    Returns:
        Reviews enriched with 'themes_neg' and 'themes_pos' fields
    """
    try:
        import anthropic
    except ImportError:
        print("ERROR: anthropic library not installed. Run: pip install anthropic", file=sys.stderr)
        print("Falling back to keyword tagger.", file=sys.stderr)
        from theme_tagger import tag_reviews
        return tag_reviews(reviews, taxonomy)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.", file=sys.stderr)
        print("Falling back to keyword tagger.", file=sys.stderr)
        from theme_tagger import tag_reviews
        return tag_reviews(reviews, taxonomy)

    client = anthropic.Anthropic(api_key=api_key)

    neg_themes = taxonomy.get("negative_themes", {})
    pos_themes = taxonomy.get("positive_themes", {})

    neg_list = "\n".join(f'- {k}: {v.get("label", k)}' for k, v in neg_themes.items())
    pos_list = "\n".join(f'- {k}: {v.get("label", k)}' for k, v in pos_themes.items())

    output = []
    batch = []
    batch_indices = []

    def flush_batch():
        if not batch:
            return
        themes_text = neg_list if batch[0]["rating"] <= 3 else pos_list
        polarity_key = "themes_neg" if batch[0]["rating"] <= 3 else "themes_pos"
        prompt = f"""Classify each review against these themes (output only the theme keys that apply):

{themes_text}

Reviews:
{json.dumps([{"i": i, "text": r["review"][:500]} for i, r in enumerate(batch)], indent=2)}

Output JSON in this exact shape:
{{"results": [{{"i": 0, "themes": ["key1", "key2"]}}, ...]}}"""

        try:
            response = client.messages.create(
                model=model,
                max_tokens=2000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text
            # Extract JSON
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip("`\n ")
            parsed = json.loads(text)
            results = {item["i"]: item.get("themes", []) for item in parsed.get("results", [])}
            for i, r in enumerate(batch):
                enriched = dict(r)
                themes_assigned = results.get(i, [])
                # Only assign valid theme keys
                valid_keys = set(neg_themes) | set(pos_themes)
                themes_assigned = [t for t in themes_assigned if t in valid_keys]
                enriched[polarity_key] = themes_assigned
                # The opposite polarity stays empty
                opposite = "themes_pos" if polarity_key == "themes_neg" else "themes_neg"
                enriched.setdefault(opposite, [])
                output.append(enriched)
        except Exception as exc:
            if verbose:
                print(f"  LLM batch failed: {exc} - falling back to keyword", file=sys.stderr)
            from theme_tagger import tag_reviews
            for r in batch:
                output.extend(tag_reviews([r], taxonomy))

    # Group by polarity to avoid mixing neg/pos themes in one batch
    neg_reviews = [r for r in reviews if r.get("rating", 0) <= 3]
    pos_reviews = [r for r in reviews if r.get("rating", 0) >= 4]

    for group in (neg_reviews, pos_reviews):
        for i, r in enumerate(group):
            batch.append(r)
            batch_indices.append(i)
            if len(batch) >= batch_size:
                flush_batch()
                if verbose:
                    print(f"  Processed {len(output)}/{len(reviews)}", file=sys.stderr)
                batch = []
                batch_indices = []
        flush_batch()
        batch = []
        batch_indices = []

    return output
