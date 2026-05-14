# Output Formats

The skill produces six formats. Pick based on what you need.

## Format selection

```bash
--formats html,pdf,excel,csv,markdown,json
```

You can mix and match. Default is `html,excel,csv` — visual + data.

## HTML

Three files:

- `executive_summary.html` — cross-store synthesis with key findings
- `playstore_deepdive.html` — Google Play deep dive
- `appstore_deepdive.html` — App Store deep dive

When only one store has data, the executive summary is replaced with a single-store version (or skipped entirely).

**Editorial design** — cream + terracotta + sage palette, Fraunces + Newsreader typography. Looks like a magazine spread, not a SaaS dashboard. Designed to be:

- Sent to clients
- Embedded in pitch decks (via PDF export)
- Shared as a link
- Published as a blog post

**Includes:**
- Masthead with sticky navigation
- "If you read nothing else" callout panel
- Stat strip with headline numbers
- Rating distribution bars
- Quarterly timeline chart
- Theme blocks with verbatim quotes (deduplicated across themes)
- Pull quote selected from emotional-weight scoring
- 4-star "Almost-Loyal" section with highlighted conditional phrases
- Cross-store comparison table
- Strategic takeaways with evidence citations
- Searchable, filterable, paginated review archive

## PDF

Same content as the HTML reports, rendered to PDF via Playwright. Good for:

- Email attachments
- Printing
- Locked client deliverables (recipient can't tweak the HTML)
- Archival snapshots

Requires `playwright install chromium`. Falls back gracefully if not available — the HTML is always there.

## Excel

`<app_slug>_reviews.xlsx` with 5–6 sheets:

| Sheet | Contents |
|---|---|
| Summary | Headline stats — totals, averages, gap, taxonomy used |
| Rating Distribution | 5 / 4 / 3 / 2 / 1 star counts per store |
| All Reviews | Combined, sorted, with theme tags as comma-separated strings |
| Themes | Theme counts per store with polarity |
| Google Play | Play-only reviews |
| App Store | iOS-only reviews |

For analysts who want to pivot, filter, and chart themselves.

## CSV

Three files:

- `playstore_reviews.csv` — Play-only
- `appstore_reviews.csv` — iOS-only
- `all_reviews.csv` — combined

Same data as the Excel "All Reviews" sheet but in three separate lightweight CSVs. Themes serialized as comma-separated strings within the cell.

Columns:
```
source, rating, date, user, country, country_code, title, review,
themes_neg, themes_pos, is_non_english, app_version, helpful_count, language
```

## Markdown

`summary.md` — single file, GitHub-flavored. Good for:

- Pasting into a PR description
- Notion or Coda pages
- Internal wiki entries
- The README of a private project tracking this competitor

**Includes:**
- Headline numbers table
- Top complaints + top praise per store
- Cross-store theme comparison table
- Three standout 1-star quotes per store
- Method + caveats footer

No editorial design — pure information density. Compact enough that a stakeholder can read it in 60 seconds.

## JSON

`full_analysis.json` — the complete analysis object. Used internally by the report generators, but exposed for downstream use.

Top-level keys:
```
{
  "taxonomy": {...},        // The taxonomy used
  "play": {...},            // Play Store aggregates
  "ios": {...},             // App Store aggregates
  "play_metadata": {...},   // Play Store app info
  "ios_metadata": {...},    // App Store app info
  "all_reviews": [...],     // Every review with theme tags
  "play_fourstar": [...],   // 4-star conditional reviews from Play
  "ios_fourstar": [...],    // 4-star conditional reviews from iOS
  "play_timeline": [...],   // Monthly review buckets, Play
  "ios_timeline": [...],    // Monthly review buckets, iOS
  "cross": {...},           // Cross-store comparison data
  "play_power_quotes": [...],
  "ios_power_quotes": [...],
  "summary": {...}          // Top-level counts
}
```

Useful for:

- Building your own visualizations
- Feeding into another tool (Streamlit, Tableau, custom dashboard)
- Comparing analyses over time
- Validating that themes were tagged how you expected

## Combining formats

Different deliverables suit different audiences in the same project:

```bash
python -m scripts.run_pipeline \
  --play com.example --appstore 123456 \
  --formats html,pdf,markdown,excel \
  --output ./reports/example
```

→ HTML for the client meeting
→ PDF for the email follow-up
→ Markdown for the internal Notion page
→ Excel for the analyst who wants to dig in

## File naming

All files land in `--output <dir>`. Filenames are consistent across runs so you can re-run and the files update in place:

```
output/example/
├── executive_summary.html
├── executive_summary.pdf
├── playstore_deepdive.html
├── playstore_deepdive.pdf
├── appstore_deepdive.html
├── appstore_deepdive.pdf
├── example_reviews.xlsx
├── playstore_reviews.csv
├── appstore_reviews.csv
├── all_reviews.csv
├── summary.md
├── full_analysis.json
└── _analysis.json    (internal — same as full_analysis but always written)
```

## Customizing the branding

The HTML reports use CSS variables for the entire palette. To match a client brand:

1. Run the pipeline normally
2. Open any HTML file
3. Find `--brand-primary` and `--brand-secondary` at the top of `<style>`
4. Replace with the client's colors
5. Re-export as PDF if needed

For repeatable rebranding, edit the `CSS` constant at the top of `scripts/generate_html.py` and commit a fork.

## Adding a `--byline`

```bash
--byline "Prepared by [Your Agency]"
```

Adds a credit line to the footer of every HTML report. Discreet but professional. Use for client deliverables where you want subtle attribution.
