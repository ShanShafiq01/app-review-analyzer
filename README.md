# App Review Analyzer

> The review report you'd pay AppFollow $300/month for, generated in 90 seconds by Claude.

A Claude skill that scrapes published reviews from the Apple App Store and Google Play Store, tags them against vertical-specific taxonomies, and produces editorial-grade analysis reports in HTML, PDF, Excel, CSV, Markdown, or JSON.

Built for production use. Handles Apple's aggressive rate-limiting. Surfaces clear messages to humans, not HTTP codes.

```
You:    Analyze reviews for Calm
Claude: [Both stores, default formats? Y]

[Step 1/5] Pulling Google Play reviews...
  us/en: +234 new reviews (total: 234)

[Step 2/5] Pulling App Store reviews...
  Rate-limited (HTTP 503). Backing off 5s — this is normal for popular apps
  Got 196 App Store reviews from 2 countries

[Step 3/5] Tagging reviews with 'health_wellness' taxonomy...
[Step 4/5] Running analysis...
[Step 5/5] Generating outputs: html, excel, csv

✓ Analysis complete for Calm
  Reviews analyzed: 234 Play + 196 App Store = 430 total

Files generated in ./output/calm:
  executive_summary.html · playstore_deepdive.html
  appstore_deepdive.html · calm_reviews.xlsx
  playstore_reviews.csv · appstore_reviews.csv · all_reviews.csv

Top three findings:
  +0.45★  iOS users rate Calm higher than Android
  62      reviews complain about subscription friction (#1 theme)
  47%     of 5-star reviews mention "sleep" or "anxiety"
```

That is not a CSV dump. That is competitive intelligence.

## Who this is for

- **Product managers** investigating competitors or doing pre-launch research
- **Founders and indie devs** monitoring their own app's reception
- **Agencies and consultants** producing client deliverables
- **Anyone** who has scrolled through 200 reviews trying to spot the pattern

## What you get

For any app on either store, in 60-180 seconds:

| Deliverable | What it is |
|---|---|
| **Executive Summary** (HTML) | Cross-store synthesis. Three headline findings. Strategic takeaways with citations. The thing you put in front of a client first. |
| **Per-store deep-dives** (HTML × 2) | Top complaints with verbatim quotes. Quarterly timeline. 4-star "Almost-Loyal" section. Searchable, filterable, paginated archive. |
| **PDF** | Print-ready version of all three reports. |
| **Excel** | 5-sheet workbook — summary, distribution, all reviews tagged, per-store. |
| **CSV** | Lightweight raw exports (one per store + combined). |
| **Markdown** | GitHub/Notion friendly summary for PRs and wikis. |
| **JSON** | Structured data for downstream processing. |

## Install

See [INSTALL.md](./INSTALL.md) for all three paths. Quick version:

### Claude Code (recommended)

```bash
git clone https://github.com/ShanShafiq01/app-review-analyzer.git \
  ~/.claude/skills/app-review-analyzer
cd ~/.claude/skills/app-review-analyzer
./setup.sh
```

Then in Claude Code: `Analyze reviews for Duolingo`

### Or as a Claude Code slash command

```
/review-analyze https://apps.apple.com/us/app/calm/id571800810
```

### Or standalone

```bash
python -m scripts.run_pipeline \
  --play com.duolingo --appstore 570060128 \
  --formats html,pdf,excel,csv,markdown,json \
  --output ./output/duolingo
```

## Production hardening (what's different about v0.2)

This is the rewrite that came out of testing against real apps at scale. v0.1 worked. v0.2 doesn't break when Apple is having a bad day.

| What | How |
|---|---|
| **Rate-limit handling** | Exponential backoff with jitter (5s, 15s, 45s ± 20%) on 429/503 |
| **Country rotation** | Pages interleaved across countries — never hammer one |
| **Retry-After header** | Honored when Apple sends it |
| **Country-less RSS fallback** | Last-resort URL if country-specific ones all fail |
| **Graceful degradation** | Partial Apple data + Play data → still produces a report |
| **Friendly errors** | "Apple is rate-limiting heavily — try again in 30 minutes" not "HTTP 503" |
| **Test fixtures** | Unit tests + integration tests against small real apps |
| **Per-format isolation** | If PDF generation fails, Excel still works |
| **Detailed progress** | Numbered steps, real-time status, no firehose of HTTP codes |

See `WORKFLOW.md` for a full diagram of inputs, steps, and outputs.

## Editorial design

The HTML reports look like a magazine spread, not a SaaS dashboard. Specifically:

- Cream + terracotta + sage palette
- Variable serif typography (Fraunces display + Newsreader body)
- Sticky masthead with section navigation
- Quarterly timeline charts with rating-mix stacking
- 4-star "Almost-Loyal" cards with conditional phrases highlighted in saffron
- Pull quotes scored from the 1-star pile on emotional weight
- Side-by-side cross-store comparison bars
- Searchable, filterable, paginated review archive
- CSS variables for the entire palette — rebrand by changing two colors

## Available taxonomies

| Taxonomy | Best for |
|---|---|
| `general` | Any app — sensible fallback |
| `health_wellness` | Fertility, meditation, fitness, mental health, nutrition |
| `fintech` | Banking, investing, crypto, payments, budgeting |
| `ecommerce` | Shopping, marketplaces, delivery, classifieds |
| `social` | Messaging, social media, dating, community |
| `productivity` | Notes, calendar, task management, work tools |
| `gaming` | Mobile games |

Use `--themes auto` and the skill picks one based on the app's store category.

## CLI reference

```
--play              Play Store package name or full URL
--appstore          App Store numeric ID or full URL
--countries         Comma-separated country codes (default: us,gb,ca,au)
--themes            Taxonomy name or 'auto' (default: general)
--formats           Comma-separated: html,pdf,excel,csv,markdown,json
--output            Output directory (default: ./output)
--app-display-name  Override the detected app name in reports
--byline            Optional credit line in report footers
--llm-tagging       Use Claude for theme tagging (requires ANTHROPIC_API_KEY)
--quiet             Suppress progress output (good for CI)
```

## Optional LLM-powered tagging

For higher accuracy, the skill can use Claude to classify reviews instead of keyword matching. Set `ANTHROPIC_API_KEY` and add `--llm-tagging`. Costs ~$0.10–$0.30 per app analysis.

Keyword tagging is the default — free, fast, reproducible.

## How it compares

|  | App Review Analyzer | AppFollow | Sensor Tower |
|---|---|---|---|
| Price | Free, MIT | $300/mo+ | $500/mo+ |
| Both stores | ✓ | ✓ | ✓ |
| Editorial HTML reports | ✓ | – | – |
| PDF/Excel/CSV/MD/JSON | ✓ | partial | partial |
| Theme taxonomies | 7 verticals + custom | generic only | custom available |
| Cross-store comparison | ✓ | ✓ | ✓ |
| 4-star "Almost-Loyal" analysis | ✓ | – | – |
| Brand customization | CSS variables | limited | available |
| Self-hosted | ✓ | – | – |

Paid tools are better at continuous monitoring (they have years of cached data). This skill is better at the moment when you need a single beautiful report, right now.

## Limits (be upfront with your stakeholders)

- App Store RSS exposes ~500 reviews per country (Apple's limit, not ours)
- Play Store may show higher total ratings than text reviews (most users tap stars without writing)
- Both stores omit star-only ratings — numbers are text reviews only
- English-only thematic tagging (non-English reviews kept in raw data, flagged)
- Apple's RSS sometimes 503s under heavy use — handled gracefully but you'll get fewer reviews when it happens

Full details in `references/known_limits.md`.

## Documentation

| File | Read when |
|---|---|
| [INSTALL.md](./INSTALL.md) | Setting up the skill |
| [WORKFLOW.md](./WORKFLOW.md) | Understanding what the skill does step by step |
| [SKILL.md](./SKILL.md) | (For Claude) — the runtime instructions Claude reads |
| [ETHICS.md](./ETHICS.md) | Before deploying for client work |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | Submitting changes |
| [CHANGELOG.md](./CHANGELOG.md) | What's new in each version |
| `references/` | Deeper docs Claude reads on demand |

## Roadmap

- v0.3 — Multilingual theme tagging via LLM
- v0.3 — Sentiment scoring per theme (not just count)
- v0.4 — Historical trend tracking (compare runs over time)
- v0.4 — Custom-branded templates for white-label
- v0.5 — Cross-app competitive comparison (X vs Y vs Z in one report)

### Repository structure

This repo is currently a single-skill repo: the repo *is* the skill, mirroring how Claude Code installs skills (`~/.claude/skills/app-review-analyzer/`).

If a second skill ships under this author, the repo will be restructured as a monorepo with skills under a `skills/` subdirectory. The migration would be mechanical (`git mv` to preserve history) and install paths would change. Until then, the flat layout keeps the README focused on what the skill *does*, not on the structure that holds it.

## Ethics

This skill scrapes only publicly available review data through each store's official public review feeds. **Do not** use it to harass developers, manipulate review systems, or republish full review text as your own analysis. See [ETHICS.md](./ETHICS.md) for the full rules.

## Contributing

PRs welcome — see [CONTRIBUTING.md](./CONTRIBUTING.md). Particularly interested in:
- Additional vertical taxonomies (real estate, education, travel, dating)
- Better non-English handling
- More accurate theme keywords (false-positive reports especially welcome)
- Performance improvements on the Play Store scraper

## License

MIT. See [LICENSE](./LICENSE). Fork it, improve it, sell services around it, embed it in your own product. The only thing prohibited by ETHICS.md is using it to harm app developers or manipulate review systems.

---

Made because a friend wanted to know what users were really saying about a fertility app, and we got tired of paying $300/month for the answer.
