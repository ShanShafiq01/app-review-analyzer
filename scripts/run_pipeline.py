"""
Pipeline orchestrator — production-grade.

Single command that scrapes, analyzes, and produces every requested output format.

Resilience design:
  - Each store fetch can fail independently — the pipeline continues with what works
  - "Apple is blocking" produces Play-only report + clear user message, not a crash
  - "Play returned nothing" produces App-only report + clear user message
  - Both stores failing produces a clear actionable error, not a stack trace
  - Progress messages are written for humans, not machines

Returns a dict with the user-presentable outcome:
    {
        "success": bool,
        "generated_files": {...},
        "warnings": [...],
        "user_message": str,
    }
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Force UTF-8 stdout/stderr — review text contains emoji, accents, CJK characters
# and would UnicodeEncodeError under LC_ALL=C or minimal-container locales otherwise.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))

from fetch_playstore import fetch_playstore_reviews, fetch_app_metadata as fetch_play_meta
from fetch_appstore import fetch_appstore_reviews, fetch_app_metadata as fetch_ios_meta
from theme_tagger import load_taxonomy, tag_reviews, suggest_taxonomy
from analyze import run_full_analysis


VALID_FORMATS = {"html", "pdf", "excel", "csv", "markdown", "md", "json"}
DEFAULT_FORMATS = ("html", "excel", "csv")


import re as _re

# Whitelists: Play Store package names are dotted alphanumerics; App Store IDs are pure digits.
# Both formats are well-defined by the stores — anything outside these patterns is invalid
# input and would only produce a 404 anyway. Validating here gives us a clear error
# message instead of a confusing failure deep in the scraper.
_PLAY_ID_PATTERN = _re.compile(r"^[a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)+$")
_IOS_ID_PATTERN = _re.compile(r"^\d+$")


def parse_url_or_id(value, kind):
    """Extract an app identifier from a URL or accept a bare ID.

    Returns the validated ID string, or None if the input is empty/invalid.
    Rejects anything that doesn't look like a real Play Store package name
    or App Store numeric ID — this prevents path-traversal-style attempts
    like "123/../" from reaching the URL templates downstream.
    """
    if not value:
        return None
    value = value.strip()

    if kind == "play":
        if "play.google.com" in value:
            import urllib.parse as urlp
            parsed = urlp.urlparse(value)
            qs = urlp.parse_qs(parsed.query)
            value = qs.get("id", [None])[0]
            if not value:
                return None
        # Validate: Play Store package names look like "com.company.app"
        if _PLAY_ID_PATTERN.match(value):
            return value
        return None

    else:  # ios
        if "apps.apple.com" in value:
            m = _re.search(r"/id(\d+)", value)
            if m:
                return m.group(1)
            return None
        # Validate: App Store IDs are pure digits
        if _IOS_ID_PATTERN.match(value):
            return value
        return None


def run_pipeline(
    play_id=None,
    appstore_id=None,
    countries=("us", "gb", "ca", "au"),
    themes_name="general",
    formats=DEFAULT_FORMATS,
    output_dir="./output",
    app_display_name=None,
    byline=None,
    use_llm=False,
    progress_callback=None,
):
    """Run the full pipeline. Always returns a result dict — never raises for
    rate limits or partial failures."""

    def _log(msg):
        if progress_callback:
            progress_callback(msg)
        else:
            print(msg, file=sys.stderr)

    result = {
        "success": False,
        "generated_files": {},
        "warnings": [],
        "user_message": "",
        "play_count": 0,
        "ios_count": 0,
    }

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not play_id and not appstore_id:
        result["user_message"] = "No app IDs provided. Pass --play <package_name> and/or --appstore <numeric_id>."
        return result

    # Validate formats
    formats = set(f.strip().lower() for f in formats)
    if "md" in formats:
        formats.add("markdown")
        formats.discard("md")
    invalid = formats - VALID_FORMATS
    if invalid:
        result["user_message"] = f"Unknown format(s): {', '.join(invalid)}. Valid: {', '.join(sorted(VALID_FORMATS))}."
        return result

    # ────────────────── Step 1: Scrape ──────────────────
    play_result = {"reviews": [], "partial": False, "warning_message": None}
    ios_result = {"reviews": [], "partial": False, "warning_message": None}
    play_metadata = {}
    ios_metadata = {}

    if play_id:
        _log(f"\n[Step 1/5] Pulling Google Play reviews...")
        play_result = fetch_playstore_reviews(
            play_id,
            locales=[(c, "en") for c in countries],
            progress_callback=progress_callback,
        )
        if play_result.get("warning_message"):
            result["warnings"].append(play_result["warning_message"])
        play_metadata = fetch_play_meta(play_id, progress_callback=progress_callback)
        result["play_count"] = len(play_result["reviews"])

    if appstore_id:
        _log(f"\n[Step 2/5] Pulling App Store reviews...")
        ios_result = fetch_appstore_reviews(
            appstore_id,
            countries=countries,
            progress_callback=progress_callback,
        )
        if ios_result.get("warning_message"):
            result["warnings"].append(ios_result["warning_message"])
        ios_metadata = fetch_ios_meta(appstore_id, progress_callback=progress_callback)
        result["ios_count"] = len(ios_result["reviews"])

    play_reviews = play_result["reviews"]
    ios_reviews = ios_result["reviews"]

    # ────────────────── Check: did we get anything? ──────────────────
    if not play_reviews and not ios_reviews:
        result["user_message"] = (
            "No reviews could be retrieved from either store. "
            "This usually means: (1) the app IDs are wrong — double check the URLs; "
            "(2) the app has no public reviews; or (3) both stores are rate-limiting "
            "right now. Try again in 20-30 minutes."
        )
        if result["warnings"]:
            result["user_message"] += "\n\nDetails:\n" + "\n".join(f"  - {w}" for w in result["warnings"])
        return result

    # Detect "we asked for both, only got one" — produce report for the one we got
    if play_id and not play_reviews:
        _log(f"\n  Note: Play Store returned no data. Proceeding with App Store only.")
    if appstore_id and not ios_reviews:
        _log(f"\n  Note: App Store returned no data. Proceeding with Play Store only.")

    # ────────────────── Step 2: Auto-detect display name + taxonomy ──────────────────
    if not app_display_name:
        app_display_name = (
            play_metadata.get("title")
            or ios_metadata.get("title")
            or "Unknown App"
        )

    if themes_name == "auto":
        category = play_metadata.get("category") or ios_metadata.get("category") or ""
        themes_name = suggest_taxonomy(category)
        _log(f"  Auto-selected taxonomy: '{themes_name}' (based on category: {category or 'unknown'})")

    # ────────────────── Step 3: Tag ──────────────────
    _log(f"\n[Step 3/5] Tagging reviews with '{themes_name}' taxonomy...")
    try:
        taxonomy = load_taxonomy(themes_name)
    except FileNotFoundError:
        result["user_message"] = (
            f"Taxonomy '{themes_name}' not found. Available: general, health_wellness, "
            f"fintech, ecommerce, social, productivity, gaming, or 'auto'."
        )
        return result

    if use_llm:
        try:
            from llm_tagger import tag_reviews_with_llm
            tag_fn = lambda revs, tax: tag_reviews_with_llm(revs, tax, verbose=True)
        except ImportError:
            _log("  LLM tagger unavailable — falling back to keyword tagging")
            tag_fn = tag_reviews
    else:
        tag_fn = tag_reviews

    play_tagged = tag_fn(play_reviews, taxonomy) if play_reviews else []
    ios_tagged = tag_fn(ios_reviews, taxonomy) if ios_reviews else []

    # ────────────────── Step 4: Analyze ──────────────────
    _log(f"\n[Step 4/5] Running analysis...")
    data = run_full_analysis(play_tagged, ios_tagged, taxonomy, play_metadata, ios_metadata)
    data["_app_name"] = app_display_name

    # Always save the analysis JSON for inspection/debugging
    (output_dir / "_analysis.json").write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    # ────────────────── Step 5: Generate ──────────────────
    _log(f"\n[Step 5/5] Generating outputs: {', '.join(sorted(formats))}")
    generated = {}

    def _try(label, fn, *args):
        try:
            return fn(*args)
        except Exception as exc:
            _log(f"  {label}: failed ({type(exc).__name__}: {exc})")
            result["warnings"].append(f"{label} generation failed: {exc}")
            return None

    if "html" in formats or "pdf" in formats:
        from generate_html import generate_html_reports
        html_files = _try("HTML", generate_html_reports, data, output_dir, app_display_name, byline)
        if html_files:
            generated["html"] = html_files
            if "pdf" in formats:
                try:
                    from generate_pdf import generate_pdf_reports
                    pdf_files = generate_pdf_reports(output_dir, output_dir)
                    if pdf_files:
                        generated["pdf"] = pdf_files
                except ImportError:
                    _log("  PDF skipped: playwright not installed (run: pip install playwright && playwright install chromium)")
                    result["warnings"].append("PDF skipped — playwright not installed")

    if "excel" in formats:
        from generate_excel import generate_excel_report
        excel_path = output_dir / f"{_slug(app_display_name)}_reviews.xlsx"
        excel_file = _try("Excel", generate_excel_report, data, excel_path)
        if excel_file:
            generated["excel"] = [excel_file]

    if "csv" in formats:
        from generate_csv import generate_csv_reports
        csv_files = _try("CSV", generate_csv_reports, data, output_dir)
        if csv_files:
            generated["csv"] = csv_files

    if "markdown" in formats:
        from generate_markdown import generate_markdown_report
        md_path = output_dir / "summary.md"
        md_file = _try("Markdown", generate_markdown_report, data, md_path, app_display_name, byline)
        if md_file:
            generated["markdown"] = [md_file]

    if "json" in formats:
        from generate_json import generate_json_export
        json_path = output_dir / "full_analysis.json"
        json_file = _try("JSON", generate_json_export, data, json_path)
        if json_file:
            generated["json"] = [json_file]

    result["success"] = True
    result["generated_files"] = generated

    # Build the user message
    msg_parts = [f"\n✓ Analysis complete for {app_display_name}"]
    msg_parts.append(f"  Reviews analyzed: {result['play_count']} Play + {result['ios_count']} App Store = {result['play_count'] + result['ios_count']} total")
    if result["warnings"]:
        msg_parts.append(f"\n⚠ Notes:")
        for w in result["warnings"]:
            msg_parts.append(f"  - {w}")
    if generated:
        msg_parts.append(f"\nFiles generated in {output_dir}:")
        for fmt, files in generated.items():
            for f in files:
                msg_parts.append(f"  [{fmt}] {Path(f).name}")
    result["user_message"] = "\n".join(msg_parts)

    _log(result["user_message"])
    return result


def _slug(name):
    import re
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return s or "app"


def main():
    parser = argparse.ArgumentParser(
        description="Scrape and analyze app store reviews",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Both stores with default formats (HTML + Excel + CSV)
  python -m scripts.run_pipeline --play com.duolingo --appstore 570060128

  # Health/wellness taxonomy, all formats
  python -m scripts.run_pipeline --play com.calm.android --appstore 571800810 \\
      --themes health_wellness --formats html,pdf,excel,csv,markdown,json

  # URLs work directly
  python -m scripts.run_pipeline \\
      --play "https://play.google.com/store/apps/details?id=com.example" \\
      --appstore "https://apps.apple.com/us/app/example/id123456"

  # Auto-detect taxonomy from category
  python -m scripts.run_pipeline --play com.x --appstore 9999 --themes auto
""",
    )
    parser.add_argument("--play", help="Play Store package name or URL")
    parser.add_argument("--appstore", help="App Store numeric ID or URL")
    parser.add_argument("--countries", default="us,gb,ca,au")
    parser.add_argument("--themes", default="general",
                        help="general/health_wellness/fintech/ecommerce/social/productivity/gaming or 'auto'")
    parser.add_argument("--formats", default="html,excel,csv",
                        help="Comma-separated: html,pdf,excel,csv,markdown,json")
    parser.add_argument("--output", default="./output")
    parser.add_argument("--app-display-name")
    parser.add_argument("--byline")
    parser.add_argument("--llm-tagging", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    play_id = parse_url_or_id(args.play, "play")
    appstore_id = parse_url_or_id(args.appstore, "ios")

    countries = [c.strip() for c in args.countries.split(",") if c.strip()]
    formats = [f.strip() for f in args.formats.split(",") if f.strip()]

    callback = (lambda m: None) if args.quiet else None

    result = run_pipeline(
        play_id=play_id,
        appstore_id=appstore_id,
        countries=countries,
        themes_name=args.themes,
        formats=formats,
        output_dir=args.output,
        app_display_name=args.app_display_name,
        byline=args.byline,
        use_llm=args.llm_tagging,
        progress_callback=callback,
    )

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
