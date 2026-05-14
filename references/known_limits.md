# Known Limitations

Surface these to clients before they ask. Most "why is this number different?" questions trace to one of these.

## Apple App Store

### ~500 reviews per country maximum

Apple's public RSS feed exposes 10 pages of ~50 reviews per page per country storefront. There is no documented way to get more through the RSS feed.

**Impact:** for popular apps with thousands of reviews per country, the skill will report 500 even when Apple's listing page shows 50,000+.

**Mitigation:** add more countries to `--countries`. Each one gives up to ~500 more. But many smaller storefronts return 0 if the app isn't listed there.

### Apple RSS occasionally returns 503

Apple rate-limits aggressive scraping. The skill retries politely (it stops trying after the first 503 per country) but if Apple is having a bad day, you'll get fewer reviews than expected.

**Mitigation:** wait a few hours and re-run. The 503 is transient.

### Date coverage drops off before mid-2021

The RSS feed has been around longer than 2021 but date metadata becomes spotty further back. For apps launched in 2018–2020, you'll see most recent reviews fully dated and older ones with empty `date` fields.

**Mitigation:** none currently. The reviews are still in the data, just without dates. The timeline chart silently skips undated reviews.

### "Total ratings" on the listing vs. text reviews

Apple's app listing page shows a total ratings count (e.g. "4.8 ★ · 12,453 ratings"). Most of those are star-only — the user tapped 5 stars but didn't write text. The RSS feed only returns reviews with text.

**Impact:** the report will say "196 reviews analysed" even if the listing shows 12,453.

**Communicate this to the user:** "The 196 number is text reviews with actual prose. The 12,453 includes star-only ratings — those have no text to analyze."

## Google Play Store

### Star-only ratings missing

Same as iOS. Google shows you a total ratings count that includes star-only taps. The `google-play-scraper` library only returns reviews with text.

**Communicate this:** "The Play Store lists 290 total ratings. We collected 174 text reviews — the gap is users who tapped stars without writing."

### Multi-locale dedup is imperfect

We pull from multiple `(country, language)` combos and dedupe by `reviewId`. Same review showing up in `us/en` and `gb/en` is deduplicated correctly. But Google sometimes assigns different `reviewId`s to the same review across very different locales (e.g., `us/en` vs `mx/es` of an English review).

**Impact:** in rare cases, very small duplication (<1% of total). Doesn't materially affect aggregates.

### Slow for popular apps

Pulling all reviews for Duolingo (~12 million users) can take 3-5 minutes. The library makes many paginated calls under the hood. The skill prints progress to stderr so you know it's still working.

### Some apps have "review history" disabled

A handful of apps have configured their listing to hide review history. The scraper returns 0 results for these. Apple's RSS doesn't have this issue.

## Theme tagging

### Keyword matching has false positives

The default tagger is case-insensitive substring matching. It will:

- Match `"bad"` inside `"isn't bad at all"` (a positive review)
- Match `"slow"` inside `"never slow"` (also positive)
- Match `"crash"` inside `"crash course"` (irrelevant)

These false positives are typically 5-10% of tags. Acceptable for aggregate analysis, problematic if you're scrutinizing individual tags.

**Mitigation:** use `--llm-tagging` for higher accuracy if you have an API key and the budget.

### English only for thematic analysis

Non-English reviews are detected via an ASCII letter ratio heuristic (<60% ASCII letters → flagged non-English). Detected non-English reviews are:

- Included in raw data exports
- Flagged with `is_non_english: true` in JSON output
- Counted in totals
- **Excluded from theme tagging** (would produce garbage tags)

**Impact:** for apps with significant non-English review volume (e.g. apps popular in Japan, Korea, Latin America), the theme analysis only reflects the English-speaking subset.

**Mitigation:** v0.2 roadmap includes multilingual tagging via LLM. For now, accept the limitation and note it in your report.

### Reviews with mixed praise and criticism

A review like "I love the design but the camera always crashes" is technically a 4-star or 5-star (depending on rating) and gets the positive themes only. The crash complaint isn't captured.

**Impact:** the 4-star "Almost-Loyal" section partially compensates for this by highlighting conditional language in 4-star reviews. But 5-star reviews with embedded complaints are missed.

**Mitigation:** none. This is an inherent limitation of polarity-based tagging.

## Cross-store comparison

### Only meaningful when both stores have meaningful data

A cross-store comparison between a Play Store with 500 reviews and an App Store with 8 reviews is technically possible but statistically silly. The skill produces the comparison anyway — it's on you to ignore it if the iOS sample is too small.

**Rule of thumb:** if either store has <20 reviews, the cross-store gap number is unreliable.

### Theme deltas are noisy at small N

When a theme has 3 mentions on Play and 1 on iOS, the percentage delta is misleadingly dramatic. The skill calculates percentages off each store's negative_total — so 3/30 (10%) vs 1/30 (3.3%) shows a +6.7 point delta which sounds significant but might just be noise.

**Mitigation:** the report shows raw counts alongside percentages. Read both.

## Reproducibility

### Each run can return slightly different reviews

Both Apple's RSS and Google's review API have non-deterministic ordering when reviews have identical timestamps. Two runs of the skill 10 minutes apart can return slightly different sets (same total, slightly different specific reviews).

**Impact:** running the analysis twice produces ~95-99% overlap, not 100%.

**Mitigation:** treat the analysis as a snapshot, not a deterministic export. If you need reproducibility, save `full_analysis.json` from the run you're publishing.

### New reviews appear constantly

For active apps, every run pulls a slightly newer dataset. The "latest review date" in the report tells you when you scraped.

## Output formats

### PDF requires Playwright + Chromium installation

`pip install playwright` plus `playwright install chromium`. If Chromium isn't installed, PDF generation fails gracefully (HTML is still produced).

### Excel doesn't include the timeline chart

The Excel output has the raw data and theme counts but doesn't render the timeline chart that appears in the HTML report. Excel users tend to chart for themselves.

### Markdown doesn't include the "Almost-Loyal" 4-star analysis

The Markdown summary is intentionally compact. The 4-star analysis with highlighted conditional phrases doesn't translate well to plain Markdown. Use HTML for that.

## Ethical limits

The skill **will not** be modified to:

- Bypass rate limits aggressively
- Pull data from non-public sources
- Identify reviewers across platforms
- Generate fake reviews

See ETHICS.md.
