"""
Excel workbook generator.

Produces a single multi-sheet XLSX with:
  - Summary: headline stats
  - Rating Distribution: by store
  - All Reviews: combined sorted by rating
  - Google Play / App Store: per-store data
  - Themes: theme counts and percentages
"""
from __future__ import annotations

import json
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    pd = None


def generate_excel_report(data, output_path):
    """Generate the Excel workbook."""
    if pd is None:
        raise ImportError("pandas required for Excel output. Install: pip install pandas openpyxl")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    play = data.get("play")
    ios = data.get("ios")
    cross = data.get("cross", {})
    all_reviews = data.get("all_reviews", [])
    taxonomy = data.get("taxonomy", {})

    # Build Summary sheet
    total = (play["total"] if play else 0) + (ios["total"] if ios else 0)
    summary_rows = [
        ("App", data.get("_app_name", "")),
        ("Total reviews collected", total),
        ("Google Play reviews", play["total"] if play else 0),
        ("App Store reviews", ios["total"] if ios else 0),
        ("", ""),
        ("Google Play avg rating", play["avg_rating"] if play else ""),
        ("App Store avg rating", ios["avg_rating"] if ios else ""),
    ]
    if cross:
        summary_rows.extend([
            ("Cross-store gap (App Store − Play)", cross.get("gap", "")),
            ("Play 1-star %", f"{cross.get('play_one_star_pct', 0):.1f}%"),
            ("App Store 1-star %", f"{cross.get('ios_one_star_pct', 0):.1f}%"),
            ("Play 5-star %", f"{cross.get('play_five_star_pct', 0):.1f}%"),
            ("App Store 5-star %", f"{cross.get('ios_five_star_pct', 0):.1f}%"),
        ])
    summary_rows.extend([
        ("", ""),
        ("Taxonomy used", taxonomy.get("label", "")),
        ("Non-English reviews", data.get("summary", {}).get("non_english_total", 0)),
    ])
    summary_df = pd.DataFrame(summary_rows, columns=["Metric", "Value"])

    # Rating distribution
    dist_rows = []
    for star_n in [5, 4, 3, 2, 1]:
        row = {"Stars": star_n}
        if play:
            row["Google Play"] = play["by_rating"].get(str(star_n), 0)
        if ios:
            row["App Store"] = ios["by_rating"].get(str(star_n), 0)
        dist_rows.append(row)
    dist_df = pd.DataFrame(dist_rows)

    # All reviews
    all_df = pd.DataFrame(all_reviews) if all_reviews else pd.DataFrame()
    if not all_df.empty:
        cols = ["source", "rating", "date", "user", "country", "title", "review", "themes_neg", "themes_pos", "is_non_english", "app_version"]
        cols = [c for c in cols if c in all_df.columns]
        all_df = all_df[cols].sort_values(["rating", "date"], ascending=[True, False])
        # Convert lists to strings for Excel display
        for col in ("themes_neg", "themes_pos"):
            if col in all_df.columns:
                all_df[col] = all_df[col].apply(lambda x: ", ".join(x) if isinstance(x, list) else str(x))

    # Themes
    theme_rows = []
    for key, label in taxonomy.get("negative_themes", {}).items():
        row = {"Theme": label, "Polarity": "Negative"}
        if play:
            row["Play count"] = play["neg_counts"].get(key, 0)
        if ios:
            row["App Store count"] = ios["neg_counts"].get(key, 0)
        theme_rows.append(row)
    for key, label in taxonomy.get("positive_themes", {}).items():
        row = {"Theme": label, "Polarity": "Positive"}
        if play:
            row["Play count"] = play["pos_counts"].get(key, 0)
        if ios:
            row["App Store count"] = ios["pos_counts"].get(key, 0)
        theme_rows.append(row)
    theme_df = pd.DataFrame(theme_rows)

    # Per-store sheets
    play_df = pd.DataFrame([r for r in all_reviews if r["source"] == "Google Play"]) if play else pd.DataFrame()
    ios_df = pd.DataFrame([r for r in all_reviews if r["source"] == "App Store"]) if ios else pd.DataFrame()

    for df in (play_df, ios_df):
        if not df.empty:
            for col in ("themes_neg", "themes_pos"):
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: ", ".join(x) if isinstance(x, list) else str(x))

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        dist_df.to_excel(writer, sheet_name="Rating Distribution", index=False)
        if not all_df.empty:
            all_df.to_excel(writer, sheet_name="All Reviews", index=False)
        theme_df.to_excel(writer, sheet_name="Themes", index=False)
        if not play_df.empty:
            play_df.to_excel(writer, sheet_name="Google Play", index=False)
        if not ios_df.empty:
            ios_df.to_excel(writer, sheet_name="App Store", index=False)

    return str(output)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    print(generate_excel_report(data, args.output))
