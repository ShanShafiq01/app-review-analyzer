"""
Markdown summary generator.

Produces a single Markdown report suitable for GitHub READMEs, Notion pages,
or pasting into a PR description. Compact, scannable, no fluff.

Security note: reviewer-supplied text is sanitized via `_md_safe` before being
embedded in the output. Without this, a review like
"Great app! [click here](https://phishing.example.com)" would render as a
clickable phishing link when an analyst publishes the Markdown report on
GitHub or Notion.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from datetime import datetime


def stars(n):
    return "★" * n + "☆" * (5 - n)


# Markdown link syntax: [text](url). Auto-linked URLs: bare http(s):// or
# javascript:/data: schemes. We neutralize all of these in user content so
# reviewer text can't smuggle clickable links into published reports.
_AUTOLINK_PATTERN = re.compile(r"(https?://|javascript:|data:|file:)", re.IGNORECASE)


def _md_safe(text: str) -> str:
    """Sanitize user-controlled text for safe Markdown embedding.

    - Escapes [ ] ( ) so reviewer text cannot form Markdown link syntax
    - Escapes ` to prevent code-injection styling
    - Inserts a zero-width space after URL schemes so they don't auto-link
    - Preserves readability — the result still looks like the original to humans
    """
    if not text:
        return ""
    # Escape link-forming punctuation
    text = text.replace("\\", "\\\\")
    for ch in ("[", "]", "(", ")", "`"):
        text = text.replace(ch, "\\" + ch)
    # Neutralize bare URL auto-linking: inserting a zero-width space (U+200B)
    # after the scheme prevents Markdown renderers from creating a link, but
    # the URL still reads naturally for humans.
    text = _AUTOLINK_PATTERN.sub(lambda m: m.group(1) + "\u200b", text)
    return text


def generate_markdown_report(data, output_path, app_name, byline=None):
    """Produce the markdown summary."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    play = data.get("play")
    ios = data.get("ios")
    cross = data.get("cross", {})
    taxonomy = data.get("taxonomy", {})

    total = (play["total"] if play else 0) + (ios["total"] if ios else 0)

    lines = []
    lines.append(f"# {app_name} — Review Audit")
    lines.append("")
    if byline:
        lines.append(f"_{byline}_")
        lines.append("")
    lines.append(f"**{total} reviews analysed** · {datetime.now().strftime('%B %Y')} · Taxonomy: `{taxonomy.get('name', 'general')}`")
    lines.append("")

    # Headline numbers
    lines.append("## Headline numbers")
    lines.append("")
    lines.append("| Store | Reviews | Avg | 1★ | 5★ |")
    lines.append("|---|---|---|---|---|")
    if play:
        lines.append(f"| Google Play | {play['total']} | {play['avg_rating']} | {play['one_star'] / play['total'] * 100:.0f}% | {play['five_star'] / play['total'] * 100:.0f}% |")
    if ios:
        lines.append(f"| App Store | {ios['total']} | {ios['avg_rating']} | {ios['one_star'] / ios['total'] * 100:.0f}% | {ios['five_star'] / ios['total'] * 100:.0f}% |")
    lines.append("")

    if cross:
        gap = cross["gap"]
        higher = "App Store" if gap > 0 else "Play Store"
        lines.append(f"**Cross-store gap:** {abs(gap):.2f} stars — {higher} users rate the same app higher.")
        lines.append("")

    # Top complaints
    if play and play["neg_counts"]:
        lines.append("## Top complaints — Google Play")
        lines.append("")
        sorted_neg = sorted(play["neg_counts"].items(), key=lambda x: -x[1])
        for key, count in sorted_neg[:6]:
            label = taxonomy["negative_themes"].get(key, key)
            pct = count / play["negative_total"] * 100 if play["negative_total"] else 0
            lines.append(f"- **{label}** — {count} mentions ({pct:.0f}% of negative reviews)")
        lines.append("")

    if ios and ios["neg_counts"]:
        lines.append("## Top complaints — App Store")
        lines.append("")
        sorted_neg = sorted(ios["neg_counts"].items(), key=lambda x: -x[1])
        for key, count in sorted_neg[:6]:
            label = taxonomy["negative_themes"].get(key, key)
            pct = count / ios["negative_total"] * 100 if ios["negative_total"] else 0
            lines.append(f"- **{label}** — {count} mentions ({pct:.0f}% of negative reviews)")
        lines.append("")

    # Top praise
    if play and play["pos_counts"]:
        lines.append("## Top praise — Google Play")
        lines.append("")
        sorted_pos = sorted(play["pos_counts"].items(), key=lambda x: -x[1])
        for key, count in sorted_pos[:5]:
            label = taxonomy["positive_themes"].get(key, key)
            pct = count / play["positive_total"] * 100 if play["positive_total"] else 0
            lines.append(f"- **{label}** — {count} mentions ({pct:.0f}% of positive reviews)")
        lines.append("")

    if ios and ios["pos_counts"]:
        lines.append("## Top praise — App Store")
        lines.append("")
        sorted_pos = sorted(ios["pos_counts"].items(), key=lambda x: -x[1])
        for key, count in sorted_pos[:5]:
            label = taxonomy["positive_themes"].get(key, key)
            pct = count / ios["positive_total"] * 100 if ios["positive_total"] else 0
            lines.append(f"- **{label}** — {count} mentions ({pct:.0f}% of positive reviews)")
        lines.append("")

    # Cross-store theme comparison
    if cross and cross.get("themes"):
        lines.append("## Cross-store theme comparison")
        lines.append("")
        lines.append("| Theme | Google Play | App Store | Skew |")
        lines.append("|---|---|---|---|")
        for t in cross["themes"][:8]:
            if t["delta"] > 4:
                skew = "→ Android"
            elif t["delta"] < -4:
                skew = "→ iOS"
            else:
                skew = "~ equal"
            lines.append(f"| {t['label']} | {t['play_pct']:.0f}% ({t['play_count']}) | {t['ios_pct']:.0f}% ({t['ios_count']}) | {skew} |")
        lines.append("")

    # Power quotes
    play_quotes = data.get("play_power_quotes", [])
    ios_quotes = data.get("ios_power_quotes", [])

    if play_quotes:
        lines.append("## Standout 1-star reviews — Google Play")
        lines.append("")
        for q in play_quotes[:3]:
            lines.append(f"> {_md_safe(q['review'])}")
            lines.append(f"> — _{_md_safe(q['user'])}, {q['rating']}-star_")
            lines.append("")

    if ios_quotes:
        lines.append("## Standout 1-star reviews — App Store")
        lines.append("")
        for q in ios_quotes[:3]:
            quote_text = _md_safe(q["review"])
            if q.get("title"):
                lines.append(f"**{_md_safe(q['title'])}**")
                lines.append("")
            lines.append(f"> {quote_text}")
            lines.append(f"> — _{_md_safe(q['user'])}, {q['rating']}-star_")
            lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("**Method:** Reviews collected via official public review feeds (Google Play, Apple iTunes RSS). Themes assigned via keyword pattern-matching against the chosen taxonomy. Non-English reviews excluded from thematic analysis but included in raw counts. No private data accessed.")
    lines.append("")
    lines.append("**Caveats:** App Store RSS is capped at ~500 reviews per country. Both stores report higher total ratings than text reviews because most users tap stars without writing.")
    lines.append("")

    output.write_text("\n".join(lines), encoding="utf-8")
    return str(output)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--app-name", required=True)
    parser.add_argument("--byline")
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    print(generate_markdown_report(data, args.output, args.app_name, args.byline))
