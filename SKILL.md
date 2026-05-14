---
name: app-review-analyzer
version: 0.3.3
license: MIT
description: Scrape and analyze App Store and Google Play Store reviews for any mobile app, then generate editorial-grade reports in HTML, PDF, Excel, CSV, Markdown, or JSON. Use whenever the user wants to analyze, audit, compare, or report on mobile app reviews — including casual phrasings like "what are users saying about X" or "pull reviews for Y", and including raw App Store / Play Store URLs. Do NOT use for general opinion questions ("is Calm a good app?") with no scraping intent — answer those from knowledge instead.
---

# App Review Analyzer

This skill turns published reviews from the Apple App Store and Google Play Store into publication-quality analysis reports — HTML, PDF, Excel, CSV, Markdown, or JSON.

## When to use

Trigger this skill when:

- The user pastes an App Store or Play Store URL with any analysis intent
- The user names an app and asks what people think of it
- The user asks for a "review audit", "review report", or "competitive analysis"
- The user wants to download or export reviews for offline analysis

**Don't** use this skill for general opinion questions ("is Calm a good app?") — answer those from knowledge or web search.

## Workflow

Follow this exact sequence for the best user experience.

### Step 1 — Identify the app

Extract the IDs from what the user provided:

- **Play Store URL** → extract the `id=` parameter (e.g. `com.proov` from `play.google.com/store/apps/details?id=com.proov`)
- **App Store URL** → extract the numeric ID after `/id` (e.g. `1574349479` from `apps.apple.com/us/app/proov/id1574349479`)
- **App name only** → web search to find the store URLs, then extract both IDs. Confirm with the user before scraping if there's any ambiguity ("I found Calm — Meditation & Sleep on both stores. Proceed?")

The `parse_url_or_id` function in `scripts/run_pipeline.py` handles URL parsing automatically — you don't need to do it manually.

### Step 2 — Ask ONE question (only when needed)

Default to running with sensible defaults. Ask only when the user's intent is ambiguous. Use `ask_user_input_v0` and combine ALL clarifications into a single call:

```
Question 1: "Which output formats?"
Options: ["HTML report only", "HTML + Excel + CSV (recommended)", "Everything (HTML + PDF + Excel + CSV + Markdown + JSON)"]
```

**Skip the question entirely when:**
- The user said "full report" / "everything" → use all formats
- The user said "just the data" / "spreadsheet" → use Excel + CSV
- The user named a specific format → use that
- The user pasted only one store URL → use both stores by default; ask only if they want single-store

**Never ask** about countries (default `us,gb,ca,au` is fine for English apps) or taxonomy (the skill auto-detects from category).

### Step 3 — Run the pipeline

```python
from scripts.run_pipeline import run_pipeline

result = run_pipeline(
    play_id="com.example",          # or None if no Play Store
    appstore_id="123456789",         # or None if no App Store
    countries=["us", "gb", "ca", "au"],
    themes_name="auto",              # auto-detects from category
    formats=["html", "excel", "csv"],
    output_dir="./output/<app_slug>",
    app_display_name="App Name",     # optional — auto-detected from metadata
)
```

Or as a shell command:

```bash
python -m scripts.run_pipeline \
  --play com.example --appstore 123456789 \
  --countries us,gb,ca,au --themes auto \
  --formats html,excel,csv \
  --output ./output/example \
  --app-display-name "Example"
```

The pipeline will print progress messages to stderr. Don't show every line to the user — just summarize at the end.

### Step 4 — Handle the result

The `run_pipeline` function returns a dict:

```python
{
    "success": True | False,
    "generated_files": {"html": [...], "csv": [...], ...},
    "warnings": ["Partial App Store data: ...", ...],
    "user_message": "Multi-line summary",
    "play_count": 170,
    "ios_count": 1500,
}
```

**On success:** present the generated files to the user, leading with the executive summary HTML (the most polished deliverable). If there were warnings, surface them clearly first.

How to present depends on the channel:

- **In claude.ai (web/desktop) — sandboxed runtime:** write outputs to `/mnt/user-data/outputs/<app_slug>/` and call `present_files` so the user gets one-click download buttons in the chat. This is the canonical Anthropic pattern for surfacing generated artifacts. If the user did not specify `--output`, default to `/mnt/user-data/outputs/<app_slug>/` when you detect the sandbox.
- **In Claude Code (CLI / VSCode extension) — local filesystem:** outputs live on the user's disk. `present_files` is unavailable. Instead, output each file as a **clickable markdown link with an absolute `file://` URL**, like `[executive_summary.html](file:///Users/you/proov-review-analysis/executive_summary.html)`. These are cmd-clickable in VSCode's integrated terminal and most modern terminals. Also include a one-line `open <path>` command (macOS) / `xdg-open <path>` (Linux) / `start <path>` (Windows) so non-clicky terminals still have a one-liner. Always use **absolute paths**, not `~/...` — `~` is not expanded inside markdown link URLs and the link won't work.

Either way, never just dump raw paths as plain text. Make the files actionable.

**On partial success (warnings present but success=True):** present files but lead with the warning. Example:

> "Done! I pulled 170 reviews from the Play Store. Apple was rate-limiting heavily — try re-running in 30 minutes for cross-store comparison. Here's what I have:"

**On failure (success=False):** show the `user_message` to the user. Common failure modes:

- Both stores rate-limited / blocked → suggest retry in 30 minutes
- Wrong app ID → ask the user to double-check the URL
- App not in any store → ask if they have a different identifier

Never show raw Python tracebacks or HTTP codes to the user. The pipeline already translates those into friendly messages.

## Output formats

| Format | When to use |
|---|---|
| `html` | Default. Three editorial reports (exec summary + per-store deep-dives). For sharing. |
| `pdf` | When the user wants something to email or print. Adds ~10s to runtime. Requires playwright. |
| `excel` | For analysts who want to slice the data. 5-sheet workbook. |
| `csv` | Lightweight raw exports (one per store + combined). |
| `markdown` | Notion/GitHub-friendly summary. Compact. |
| `json` | Structured data for downstream processing. |

## Theme taxonomies

Seven verticals ship with the skill in `templates/themes/`:

- `general` — works for any app
- `health_wellness` — fertility, meditation, fitness, mental health, nutrition
- `fintech` — banking, investing, crypto, payments
- `ecommerce` — shopping, marketplaces, delivery
- `social` — messaging, social media, dating
- `productivity` — notes, calendar, task management
- `gaming` — mobile games

Use `--themes auto` and the skill picks one from the app's store category. Override with a specific name when the auto-pick is wrong.

See `references/theme_taxonomies.md` for the schema and how to add custom ones.

## Rate-limit handling (already built-in)

The pipeline handles all of this automatically:

- **Exponential backoff with jitter** (5s, 15s, 45s ± 20%) on 429/503
- **Country rotation** — pages are interleaved across countries so we don't hammer one
- **Retry-After header** respected when Apple sends it
- **Country-less RSS fallback** when all country-specific URLs fail
- **Graceful degradation** — pipeline always produces what it could get, never crashes
- **Friendly user messages** like "Apple is rate-limiting heavily — wait 30 minutes" instead of HTTP codes

You don't need to do anything special for rate limits. The pipeline returns `partial: True` and `warning_message` if Apple blocked part of the request — just surface those to the user.

## Optional LLM-powered tagging

For higher accuracy (~$0.10–$0.30 per app), pass `use_llm=True` or `--llm-tagging`. Requires `ANTHROPIC_API_KEY`. Falls back to keyword tagging on any API error.

## Examples

See `references/examples.md` for complete invocations including:

- Both stores, default formats
- Health/wellness app with full output
- Auto-detected taxonomy
- URL inputs (paste directly from browser)
- Single store only
- Custom branding with `--byline`
- LLM-powered tagging

## Common patterns

**User says "analyze reviews for Calm":**
1. Web search to find Calm's Play Store + App Store URLs
2. Extract IDs (`com.calm.android` and `571800810`)
3. Ask one question about formats (or run with defaults if "full" / "analysis report" was implied)
4. Run pipeline with `themes=auto` (will pick health_wellness)
5. Present files; lead with executive summary HTML

**User pastes a Play Store URL only:**
1. Extract the package name
2. Ask: "Want both stores? I can search for the App Store version too, or run Play-only."
3. If they want both, web search for App Store version
4. Run pipeline with what we have

**User says "compare reviews for Headspace and Calm":**
1. Run the pipeline twice (one per app), output dirs `headspace/` and `calm/`
2. Present both report packages
3. In chat, synthesize: "Headspace averages 4.6★ on both stores. Calm 4.5★ on Play, 4.7★ on App Store. Headspace's #1 complaint is X; Calm's is Y."

**User says "what do people say about Notion?":**
1. Same as the first pattern — find IDs, run with defaults, present files
2. Briefly summarize the key findings in chat (top 3 complaints + top praise)

## What this skill never does

- Scrape private data (only public review feeds)
- Generate fake reviews
- Help identify reviewers across platforms
- Bypass rate limits aggressively

See `ETHICS.md` for the full rules and surface them to the user when the request approaches the boundary.

## Files

- `scripts/run_pipeline.py` — main entry point
- `scripts/_http.py` — shared rate-limit-aware HTTP layer
- `scripts/fetch_playstore.py` / `fetch_appstore.py` — scrapers
- `scripts/theme_tagger.py` / `llm_tagger.py` — classification
- `scripts/analyze.py` — analysis engine
- `scripts/generate_*.py` — per-format report builders
- `templates/themes/*.json` — taxonomies
- `references/*.md` — deep documentation (read these when the user asks something the SKILL.md doesn't cover)
