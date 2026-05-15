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
        "top_findings": [],
    }

    # Track whether the caller explicitly chose an output dir. We use this below
    # to decide if it's safe to re-route to the claude.ai sandbox path. If the
    # caller passed an explicit path, we respect it (and warn if it won't render).
    _user_set_output_dir = str(output_dir).rstrip("/") not in (".", "./output", "output")
    output_dir = Path(output_dir)
    # Note: mkdir is deferred until after app_display_name is resolved so we can
    # re-route to /mnt/user-data/outputs/<slug>/ on claude.ai before creating dirs.

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

    # ─── claude.ai sandbox path auto-resolution ───
    # claude.ai web's chat UI only displays files written under /mnt/user-data/outputs/.
    # Files written anywhere else exist in the sandbox filesystem but the right-panel
    # viewer reports "File could not be read. It may have been deleted or moved, or it
    # lives outside the session folder." This block detects the sandbox and re-routes
    # the default output_dir to a path the chat UI can serve. If the caller explicitly
    # set output_dir to something outside the sandbox path, we respect their choice
    # but log a clear warning.
    SANDBOX_OUTPUTS = Path("/mnt/user-data/outputs")
    if SANDBOX_OUTPUTS.is_dir():
        if not _user_set_output_dir:
            # Caller didn't override — auto-route to the path the sandbox UI can read.
            output_dir = SANDBOX_OUTPUTS / _slug(app_display_name)
            _log(f"  [claude.ai sandbox] outputs auto-routed to {output_dir}")
        elif not str(output_dir.resolve()).startswith(str(SANDBOX_OUTPUTS)):
            warn_msg = (
                f"output_dir '{output_dir}' is outside /mnt/user-data/outputs/ — "
                "files will be invisible in claude.ai's right-panel viewer "
                "(\"File could not be read... lives outside the session folder\"). "
                "Pass output_dir='/mnt/user-data/outputs/<app_slug>/' to fix."
            )
            _log(f"  WARNING: {warn_msg}")
            result["warnings"].append(warn_msg)

    # Now safe to create the directory — we know its final path.
    output_dir.mkdir(parents=True, exist_ok=True)

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

    # ────────────────── Post-process: inject Downloads section into HTML ──────────────────
    # Runs AFTER every other format finishes, so the Downloads grid lists actual
    # generated files (xlsx, csv, json, md) — not predicted ones. Failed formats
    # are simply absent from the section, which degrades cleanly.
    primary_html = None
    if "html" in formats and generated.get("html"):
        try:
            from generate_html import inject_downloads
            inject_downloads(output_dir)
        except Exception as exc:
            _log(f"  Downloads section injection failed ({type(exc).__name__}: {exc}) — HTML still works")

        # Prefer executive_summary.html as the file to auto-open / surface.
        # Fall back to the first deep-dive if no executive (single-store case).
        for fname in ("executive_summary.html", "playstore_deepdive.html", "appstore_deepdive.html"):
            candidate = output_dir / fname
            if candidate.exists():
                primary_html = candidate
                break

    # Surface the primary report so main() (or any caller) can auto-open it.
    # We don't open here — that's main()'s responsibility, gated on TTY + --no-open.
    # Keeping the side effect out of the library function so programmatic callers
    # don't get a browser window they didn't ask for.
    if primary_html and primary_html.exists():
        result["primary_output"] = str(primary_html.resolve())

    # v0.4.4: also surface the resolved output directory so main() can auto-open
    # it in the user's native file manager (Finder / Explorer / xdg-open) alongside
    # the existing browser auto-open. Same gating: TTY + --no-open + --quiet.
    # Skipped on claude.ai sandbox (the sandbox isn't a TTY).
    result["output_dir"] = str(output_dir.resolve())

    # Surface top_findings on the result dict. Claude reads these structured
    # findings from the result dict and lifts them verbatim into its chat reply
    # (per the literal mockups in SKILL.md). Data-grounded, never invented.
    # May be an empty list for small apps with no clear patterns — that's fine,
    # SKILL.md tells Claude to omit the findings block in that case.
    result["top_findings"] = data.get("top_findings", [])

    # ────────────────── Build the user message ──────────────────
    # Format matches the literal mockup in SKILL.md so Claude can lift it
    # directly into chat. Four-part structure (v0.4.0):
    #   1. Result headline      — concrete numbers, what happened
    #   2. Top findings         — only if compute_top_findings returned >=1
    #   3. File affordance      — single copy-friendly open command
    #   4. (Optional next step) — handled by Claude in chat, not in user_message
    total_count = result["play_count"] + result["ios_count"]
    msg_parts = [
        f"\n✓ Pulled {result['play_count']} Play Store + {result['ios_count']} App Store "
        f"reviews for {app_display_name} ({total_count} total)."
    ]

    if result["top_findings"]:
        msg_parts.append("\nTop findings:")
        for finding in result["top_findings"]:
            msg_parts.append(f"  • {finding}")

    if result["warnings"]:
        msg_parts.append("\nNotes:")
        for w in result["warnings"]:
            msg_parts.append(f"  - {w}")

    if generated:
        # v0.4.4: never include the directory path here. claude.ai's chat client
        # auto-renders path-shaped strings as clickable, but only individual files
        # render in the right-panel viewer — clicking a folder path produces
        # "File could not be read... lives outside the session folder." The file
        # count is informational only; the actual files are surfaced via
        # result["generated_files"] (per-format) and result["primary_output"]
        # (the executive summary's absolute path) for callers that need them.
        file_count = sum(len(v) for v in generated.values())
        plural = "s" if file_count != 1 else ""
        msg_parts.append(f"\n{file_count} file{plural} generated.")

    # File affordance: single copy-friendly open command. Filenames-as-text in
    # chat don't actually open files in any context (claude.ai web blocks
    # file:// from https origin; VSCode chat opens HTML as source; terminals
    # can't navigate paths). The open command works everywhere. Once the HTML
    # is open, its Downloads section gives one-click access to xlsx/csv/json/md.
    if primary_html and primary_html.exists():
        opener = "open" if sys.platform == "darwin" else ("start" if sys.platform == "win32" else "xdg-open")
        msg_parts.append(f"\nThe executive summary should have opened in your browser. If not, run:")
        msg_parts.append(f"  {opener} {primary_html.resolve()}")

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
  python -m scripts.run_pipeline --play com.example.app --appstore 1234567890

  # Health/wellness taxonomy, all formats
  python -m scripts.run_pipeline --play com.example.healthapp --appstore 1234567890 \\
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
    parser.add_argument("--no-open", action="store_true",
                        help="Don't auto-open the executive summary in a browser when finished.")
    parser.add_argument("--no-update-check", action="store_true",
                        help="Don't check GitHub for a newer release. (Cached 24h; fails silently otherwise.)")
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

    # Auto-open the primary report in a browser when we're in interactive use.
    # Skipped when: user passed --no-open, --quiet, or stdout/stdin is not a TTY (CI, pipes).
    primary = result.get("primary_output")
    if (primary
            and not args.no_open
            and not args.quiet
            and sys.stdout.isatty()
            and sys.stdin.isatty()):
        try:
            import webbrowser
            # Path.as_uri() correctly handles Windows drive letters and backslashes
            # (file:///C:/Users/...). String-concat of f"file://{path}" produces an
            # invalid URI on Windows and most browsers silently refuse to open it.
            webbrowser.open(Path(primary).as_uri())
        except Exception:
            pass  # opening is a nicety, not a guarantee

    # v0.4.4: Auto-reveal the output folder in the user's native file manager
    # alongside the browser auto-open. Answers the "can we open Finder here?"
    # question for Claude Code users. Same gating as the browser block above —
    # skipped in CI, headless, --no-open, --quiet, and in the claude.ai sandbox
    # (which doesn't pass the TTY check anyway, and has no file manager UI).
    output_dir_str = result.get("output_dir")
    if (output_dir_str
            and not args.no_open
            and not args.quiet
            and sys.stdout.isatty()
            and sys.stdin.isatty()):
        try:
            import subprocess
            if sys.platform == "darwin":
                subprocess.Popen(["open", output_dir_str])
            elif sys.platform == "win32":
                subprocess.Popen(["explorer", output_dir_str])
            else:
                # Linux / BSD / other Unix — xdg-open is the freedesktop standard.
                # Fails silently if xdg-utils isn't installed (headless containers,
                # minimal distros). The user can still copy-paste the open command
                # from the user_message instead.
                subprocess.Popen(["xdg-open", output_dir_str])
        except Exception:
            pass  # revealing the folder is a nicety, not a guarantee

    # Update-check banner. Cached for 24h, fails silently on any error
    # (network down, repo not yet public, parse failure). Only prints when a
    # newer version is actually available — never spams the user.
    if not args.no_update_check and not args.quiet:
        try:
            from update_check import check_for_update, format_banner
            info = check_for_update()
            if info and info.update_available:
                install_dir = Path(__file__).resolve().parent.parent
                print(format_banner(info, install_dir=install_dir), file=sys.stderr)
        except Exception:
            pass  # update check is best-effort; never block the pipeline

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
