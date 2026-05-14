# Workflow — what goes in, what comes out

This doc walks through exactly what the skill does, what it asks, and what you get. Read this if you want to know how the skill behaves before installing it.

## The 30-second version

```
                ┌─────────────────────────────────────┐
                │ INPUT — what the user provides      │
                │                                     │
                │  • Play Store URL or package name   │
                │  • App Store URL or numeric ID      │
                │  • or just an app name              │
                │  • (Claude figures out the rest)    │
                └─────────────────┬───────────────────┘
                                  │
                                  ▼
                ┌─────────────────────────────────────┐
                │ ONE QUESTION (if needed)            │
                │                                     │
                │  Which output formats?              │
                │    □ HTML only                      │
                │    ☑ HTML + Excel + CSV (default)   │
                │    □ Everything (also PDF, MD, JSON)│
                └─────────────────┬───────────────────┘
                                  │
                                  ▼
                ┌─────────────────────────────────────┐
                │ PIPELINE (60–180 seconds)           │
                │                                     │
                │  1. Scrape Play Store ✓             │
                │  2. Scrape App Store  ✓             │
                │  3. Tag with taxonomy ✓             │
                │  4. Analyze           ✓             │
                │  5. Generate outputs  ✓             │
                └─────────────────┬───────────────────┘
                                  │
                                  ▼
                ┌─────────────────────────────────────┐
                │ OUTPUT — files in ./output/<app>/   │
                │                                     │
                │  • executive_summary.html  (the     │
                │    headline document, ~30KB)        │
                │  • playstore_deepdive.html (~230KB) │
                │  • appstore_deepdive.html  (~300KB) │
                │  • <app>_reviews.xlsx      (~80KB)  │
                │  • playstore_reviews.csv            │
                │  • appstore_reviews.csv             │
                │  • all_reviews.csv                  │
                │  • summary.md       (if requested)  │
                │  • full_analysis.json (always)      │
                └─────────────────────────────────────┘
```

## Inputs in detail

The skill accepts the app in any of these forms:

### Play Store

```
com.example.app                                            ← package name
https://play.google.com/store/apps/details?id=com.example.app ← full URL
https://play.google.com/store/apps/details?id=com.x&hl=en  ← URL with extra params
```

### App Store

```
1234567890                                                 ← numeric ID
https://apps.apple.com/us/app/your-app/id1234567890        ← full URL
https://apps.apple.com/gb/app/your-app/id1234567890?at=... ← URL with tracking
```

### App name only

```
"Your App Name"
"the <category> app called <name>"
"that fertility tracker called <name>"
```

Claude does a web search to find both store URLs, extracts IDs, and confirms with the user if there's ambiguity.

### Two apps for comparison

```
"Compare Headspace and Calm"
"How do users rate Robinhood vs E*Trade?"
```

Claude runs the pipeline twice (one per app) in separate output directories.

## The one question

Claude asks **at most one** question, and only when the user's intent is ambiguous. The question is:

> **Which output formats do you want?**
> - HTML only
> - HTML + Excel + CSV  *(recommended — default)*
> - Everything (HTML + PDF + Excel + CSV + Markdown + JSON)

Claude skips this question entirely when:

- The user said "full report" → uses all formats
- The user said "just the data" / "spreadsheet" → Excel + CSV
- The user named a specific format ("generate a PDF") → that format
- The user is in a hurry / pasted just a URL → default

**Claude never asks** about:
- Countries (default `us,gb,ca,au` is fine for English apps)
- Taxonomy (auto-detected from app category)
- Theme tagging method (keyword is the default — LLM only if user has API key set)
- Brand colors / byline (uses neutral defaults)

## Pipeline steps in detail

### Step 1 — Scrape Google Play

- Uses `google-play-scraper` library
- Pulls across multiple sort orders (newest, most relevant, by rating)
- Pulls from each requested country/language combo
- Deduplicates by `reviewId`
- Typical result: 100-1000 reviews depending on app popularity
- Time: 10-60 seconds for most apps

**Failure modes (all handled):**
- App not found → returns empty list with warning
- Network error → skips that locale, continues with others
- Google rate-limiting → very rare; skipped gracefully

### Step 2 — Scrape App Store

- Uses Apple's public RSS feed
- Pulls up to 10 pages × ~50 reviews per country
- **Country rotation:** interleaves pages across countries (not 10 pages of US then 10 of UK — that triggers rate limits)
- **Exponential backoff** on 429/503: waits 5s, 15s, 45s with ±20% jitter
- **Honors Retry-After** header when Apple sends one
- **Fallback URL** (`itunes.apple.com/rss/customerreviews/...` without country) if country-specific endpoints all fail
- Typical result: 200-2000 reviews depending on app popularity and country coverage
- Time: 20-90 seconds

**Failure modes (all handled gracefully):**
- Apple rate-limiting one country → marks that country blocked, continues with others
- Apple rate-limiting all countries → tries fallback URL, then returns what was collected
- App not on App Store → returns empty list with friendly message
- Both stores fail → pipeline returns clear error, no crash

### Step 3 — Thematic tagging

- Loads the chosen taxonomy from `templates/themes/*.json`
- Inheritance resolved (e.g., `health_wellness` extends `general`)
- Each review tagged against negative themes (if rating ≤ 3) or positive themes (if rating ≥ 4)
- Non-English reviews detected via ASCII letter ratio and excluded from theme tagging (still kept in raw data)
- Time: 1-2 seconds for most datasets

**Optional LLM tagging:** if `--llm-tagging` is set and `ANTHROPIC_API_KEY` exists, uses Claude Haiku for higher accuracy. Costs ~$0.10–$0.30 per app. Falls back to keyword tagging on API error.

### Step 4 — Analysis

Computes everything the report generators need:

- Rating distribution per store
- Theme counts and example quotes (deduplicated across themes — no review appears twice)
- Quarterly timeline of review volume + rating mix
- 4-star "Almost-Loyal" extraction (reviews with conditional language: "but", "wish", "would be")
- Cross-store comparison (theme prevalence, gap analysis, platform skew)
- Power-quote selection (1-star reviews scored on emotional weight)

Time: < 1 second.

### Step 5 — Output generation

Each requested format is generated:

| Format | Filename | Built by |
|---|---|---|
| HTML | `executive_summary.html`, `playstore_deepdive.html`, `appstore_deepdive.html` | `generate_html.py` |
| PDF | Same filenames with `.pdf` | `generate_pdf.py` (Playwright) |
| Excel | `<app_slug>_reviews.xlsx` | `generate_excel.py` (openpyxl) |
| CSV | `playstore_reviews.csv`, `appstore_reviews.csv`, `all_reviews.csv` | `generate_csv.py` |
| Markdown | `summary.md` | `generate_markdown.py` |
| JSON | `full_analysis.json` | `generate_json.py` |

If one format fails (e.g., Playwright not installed), the others still work and a warning is added to the result.

## Outputs in detail

### `executive_summary.html` — the headline document

What's inside:

- Editorial masthead with app name
- "Three findings that should shape the roadmap" — dark callout panel with the three most important insights
- Side-by-side platform comparison (Play vs iOS averages, 1-star/5-star distributions)
- Theme-by-theme comparison table with platform skew arrows
- Four strategic takeaways with evidence citations

Size: ~30-40KB. Reads top-to-bottom in 3 minutes.

### `playstore_deepdive.html` / `appstore_deepdive.html`

What's inside per store:

- Stat strip (avg rating, 1-star %, 5-star %, negative review count)
- Rating distribution chart
- Quarterly timeline showing review volume + mix over time
- Top 6 complaint themes with 3 verbatim quote examples each (deduplicated)
- Pull quote — single most emotionally resonant 1-star review
- "Almost-Loyal" section — 4-star reviewers with conditional language highlighted
- Top 5 praise themes with examples
- Strategic takeaways
- **Searchable, filterable, paginated archive** of every review in the data

Size: 200-300KB depending on review count.

### `<app>_reviews.xlsx` — the analyst's workbook

Five-to-six sheets:

| Sheet | Contents |
|---|---|
| Summary | Headline metrics |
| Rating Distribution | Star counts per store |
| All Reviews | Combined, sorted, theme-tagged |
| Themes | Theme counts with polarity |
| Google Play | Play-only reviews |
| App Store | iOS-only reviews |

For analysts who want to pivot the data themselves.

### `*.csv` — lightweight raw export

Three files:

- `playstore_reviews.csv` — Play-only
- `appstore_reviews.csv` — App Store-only
- `all_reviews.csv` — combined

Columns:
```
source, rating, date, user, country, country_code, title, review,
themes_neg, themes_pos, is_non_english, app_version, helpful_count, language
```

Themes serialized as comma-separated strings within the cell.

### `summary.md` — GitHub / Notion friendly

Compact markdown with:
- Headline numbers table
- Top complaints + top praise per store
- Cross-store theme comparison table
- Three standout 1-star quotes per store
- Method + caveats footer

Designed to paste into a PR description, Notion page, or internal wiki.

### `full_analysis.json` — structured data

Everything the report generators consume — every review, every aggregate, every analytical derivative — in one structured file. Useful for:

- Building your own visualizations
- Feeding into another tool
- Comparing analyses over time
- Validating that themes were tagged how you expected

## Progress messages the user sees

The pipeline writes friendly messages to stderr:

```
[Step 1/5] Pulling Google Play reviews...
Fetching Google Play reviews for com.proov...
  us/en: +170 new reviews (total: 170)
  Got 170 Play Store reviews total

[Step 2/5] Pulling App Store reviews...
Fetching App Store reviews for app ID 1574349479...
  Rate-limited (HTTP 503). Backing off 5s — this is normal for popular apps
  Got 196 App Store reviews from 2 countries

[Step 3/5] Tagging reviews with 'health_wellness' taxonomy...

[Step 4/5] Running analysis...

[Step 5/5] Generating outputs: html, excel, csv

✓ Analysis complete for Proov Fertility
  Reviews analyzed: 170 Play + 196 App Store = 366 total

Files generated in ./output/proov:
  [html] executive_summary.html
  [html] playstore_deepdive.html
  [html] appstore_deepdive.html
  [excel] proov_fertility_reviews.xlsx
  [csv] playstore_reviews.csv
  [csv] appstore_reviews.csv
  [csv] all_reviews.csv
```

No raw HTTP codes, no Python tracebacks, no internal jargon.

## What happens when things go wrong

### Apple is rate-limiting heavily

User sees:
> ⚠ Partial App Store data: 2 of 4 countries were rate-limited by Apple. Got 50 reviews from 2 countries. Try again in 30 minutes for full coverage.

The pipeline still generates a complete report from whatever was collected.

### Both stores returned nothing

User sees:
> ✗ No reviews could be retrieved from either store. This usually means: (1) the app IDs are wrong — double check the URLs; (2) the app has no public reviews; or (3) both stores are rate-limiting right now. Try again in 20-30 minutes.

The pipeline exits with a non-zero code so CI/automation can detect failure.

### One format generator crashed

User sees:
> ⚠ Notes:
>   - PDF skipped — playwright not installed
>
> Files generated:
>   [html] executive_summary.html
>   [excel] reviews.xlsx

Other formats still work. The pipeline continues.

## Re-running

Just run again. The skill always overwrites the output directory's files. To preserve a previous run, use a different `--output` directory or rename the folder before re-running.

There's no caching by default — every run re-scrapes. This is intentional: app reviews change constantly and stale data is worse than slow data.
