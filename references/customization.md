# Customization

What you can change without touching code.

## CLI flags reference

```
--play              Play Store package name or full URL
--appstore          App Store numeric ID or full URL
--countries         Comma-separated country codes (default: us,gb,ca,au)
--themes            Taxonomy name or 'auto' to detect from category
--formats           Comma-separated: html,pdf,excel,csv,markdown,json
--output            Output directory (default: ./output)
--app-display-name  Override the detected app name in reports
--byline            Optional byline shown in report footers
--llm-tagging       Use Claude for theme tagging (requires ANTHROPIC_API_KEY)
--quiet             Suppress progress output
```

## Color customization

The HTML output uses CSS variables. To rebrand:

**Option 1: Edit the CSS in the generated file** (one-off):

```css
:root {
  --brand-primary: #1A4D8F;    /* was terracotta — now navy */
  --brand-secondary: #C8651A;  /* was sage — now orange */
}
```

Find these lines near the top of any generated HTML's `<style>` block. Change and save.

**Option 2: Edit the source** (repeatable):

Open `scripts/generate_html.py`, find the `CSS` constant near the top, change the `--brand-primary` and `--brand-secondary` values. All future runs use the new palette.

**The full CSS variable list:**

```css
--bg               /* Page background — cream */
--bg-deep          /* Slightly darker bg used for empty bars */
--card             /* Card background */
--ink              /* Body text — near-black */
--ink-soft         /* Secondary text */
--ink-mute         /* Tertiary text, labels */
--rule             /* Hairline borders */
--brand-primary    /* Negative accent — terracotta */
--brand-primary-deep
--brand-secondary  /* Positive accent — sage */
--brand-secondary-deep
--saffron          /* Neutral / star color */
```

## Font customization

The reports use Google Fonts (Fraunces + Newsreader). To swap:

1. Open `scripts/generate_html.py`
2. Find the `FONTS` constant
3. Replace the Google Fonts link with your own
4. Update the `font-family` values throughout the CSS

For a more system-y look:

```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
```

## Byline

```bash
--byline "Competitive research by ACME Inc"
```

Adds a credit line below the app name in every HTML report footer. Keep it short — under 40 characters.

## Country list

The defaults (`us,gb,ca,au`) cover the four largest English-language storefronts. Reasons to change:

- **More coverage for a global app:** Add `nz,ie,in,za,sg`
- **Specific market focus:** `--countries us` for US-only
- **Non-English app:** add the relevant country codes; reviews will be flagged `is_non_english` for theme analysis but still appear in raw data

The country list applies to both stores. Apple's RSS feed silently returns nothing for many countries where the app isn't listed — that's normal.

## Sleep delays

If you want to be even more conservative (perhaps you're scraping in a CI environment and want to be a very good citizen):

```python
# In scripts/fetch_playstore.py, top of fetch_playstore_reviews():
sleep_between=0.5    # default is 0.2

# In scripts/fetch_appstore.py:
sleep_between=0.5    # default is 0.3
```

If you want to go faster — don't. The rate limits will hit you and the skill will return fewer results.

## Page caps

App Store RSS exposes up to 10 pages × ~50 reviews per country. You can cap lower:

```python
fetch_appstore_reviews(app_id, max_pages_per_country=5)  # ~250 instead of ~500
```

Useful for quick iteration during development.

## Skipping the cache

Currently there's no built-in caching — every run re-scrapes from scratch. If you want to add caching for development, the simplest approach:

```python
import json
from pathlib import Path

cache_path = Path(f"/tmp/{app_id}_play.json")
if cache_path.exists():
    reviews = json.loads(cache_path.read_text())
else:
    reviews = fetch_playstore_reviews(app_id, ...)
    cache_path.write_text(json.dumps(reviews))
```

(Maintainers haven't built this in because it tends to get out of date and we'd rather see "is the data fresh?" be a deliberate decision.)

## LLM-powered tagging

For higher-accuracy theme classification, set `ANTHROPIC_API_KEY` and add `--llm-tagging`:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python -m scripts.run_pipeline \
  --play com.example --appstore 123456 \
  --themes general --llm-tagging \
  --formats html,csv
```

What changes:
- Theme tagging uses Claude Haiku via the Anthropic API
- Costs roughly $0.10–$0.30 per app analysis
- Better at catching context-dependent themes ("the app costs too much for what it does" → pricing, not generic complaint)
- Slower (each batch of 10 reviews = one API call)

The skill falls back to keyword tagging on any API error.

## Adding a new taxonomy

See `theme_taxonomies.md` — short version: copy `general.json`, edit, save as `templates/themes/your_name.json`, use with `--themes your_name`.

## Excluding non-English reviews entirely

By default, non-English reviews are included in raw data exports but excluded from theme analysis. If you want them removed completely:

```python
# In your own wrapper script
from scripts.fetch_playstore import fetch_playstore_reviews
reviews = fetch_playstore_reviews("com.example")
reviews = [r for r in reviews if not is_non_english(r.get("review", ""))]
```

We don't expose a CLI flag for this because it's destructive — once filtered out, those reviews are gone from the pipeline.

## Including more or fewer themes in the report

The HTML reports show:
- Top 6 negative themes
- Top 5 positive themes
- Top 6 4-star "Almost-Loyal" cards

To change these limits, edit `scripts/generate_html.py`:

```python
for i, (key, count) in enumerate(neg_sorted[:6], 1):   # change 6
for i, (key, count) in enumerate(pos_sorted[:5], 1):   # change 5
render_fourstar_cards(fourstars, max_cards=6)          # change 6
```

## Output file names

Filenames are hardcoded for consistency. If you want custom names, the simplest path is to rename the files after generation in a shell wrapper:

```bash
python -m scripts.run_pipeline --play ... --output ./output/x
mv ./output/x/executive_summary.html ./output/x/client_name_2026.html
```

## Logging

The pipeline writes progress to stderr. To log to a file:

```bash
python -m scripts.run_pipeline ... 2> run.log
```

For quiet operation:

```bash
python -m scripts.run_pipeline --quiet ...
```
