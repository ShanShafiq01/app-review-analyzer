"""
CSV report generator — lightweight raw exports.

Produces two CSVs (one per store) plus a combined CSV with theme tags.
Useful for analysts who want to slice the data in Excel/Sheets/pandas themselves.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path


CSV_COLUMNS = [
    "source", "rating", "date", "user", "country", "country_code",
    "title", "review", "themes_neg", "themes_pos",
    "is_non_english", "app_version", "helpful_count", "language",
]


def write_csv(reviews, path):
    """Write a list of review dicts to a CSV file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for r in reviews:
            row = dict(r)
            # Serialize list fields as comma-separated strings
            for col in ("themes_neg", "themes_pos"):
                if isinstance(row.get(col), list):
                    row[col] = ",".join(row[col])
            writer.writerow(row)
    return str(path)


def generate_csv_reports(data, output_dir):
    """Generate per-store and combined CSV exports."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    all_reviews = data.get("all_reviews", [])
    play_reviews = [r for r in all_reviews if r["source"] == "Google Play"]
    ios_reviews = [r for r in all_reviews if r["source"] == "App Store"]

    written = []
    if play_reviews:
        written.append(write_csv(play_reviews, output / "playstore_reviews.csv"))
    if ios_reviews:
        written.append(write_csv(ios_reviews, output / "appstore_reviews.csv"))
    if all_reviews:
        written.append(write_csv(all_reviews, output / "all_reviews.csv"))

    return written


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text())
    for f in generate_csv_reports(data, args.output):
        print(f)
