# Changelog

All notable changes documented here. Format roughly follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.1] — 2026-05-14

Security audit release. See [SECURITY.md](./SECURITY.md) for the full audit.

### Security

- **Whitelist validation on app IDs.** `parse_url_or_id` now rejects inputs that don't match the expected Play Store package name pattern (`com.x.y`) or App Store numeric pattern (`12345`). Prevents path-traversal-shaped inputs like `123/../admin` from reaching URL templates downstream.
- **Markdown injection prevention.** Reviewer-controlled text in `summary.md` output is now sanitized via `_md_safe()` — escapes Markdown link punctuation (`[ ] ( )` and backticks) and inserts zero-width spaces after URL schemes so phishing links in reviews can't auto-link when reports are published on GitHub or Notion.
- **Added [SECURITY.md](./SECURITY.md)** documenting threat model, checks performed, what was found, and ongoing privacy considerations.

### No breaking changes

All legitimate inputs continue to work. Tests cover both validation acceptance (real package names, real numeric IDs, real URLs) and rejection (path traversal, script tags, javascript schemes, command injection patterns).

---

## [0.2.0] — 2026-05-14

Production-hardening release. Everything still works, just doesn't break under stress.

### Added

- **Shared HTTP layer** (`scripts/_http.py`) with `FetchSession` class — exponential backoff with jitter, retry-after honoring, consecutive-failure tracking, progress callbacks
- **Country rotation for App Store scraper** — interleaves pages across countries instead of pulling all 10 pages of one country before the next (the latter triggers rate limits faster)
- **Country-less RSS fallback URL** — when all country-specific endpoints fail, tries `itunes.apple.com/rss/customerreviews/...` (no country) as a last resort. Defaults to US data
- **Graceful partial-data handling** — pipeline always produces what it could collect. Apple blocks 3 of 4 countries? You get a report from the 1 that worked, plus a clear warning
- **User-friendly progress messages** — numbered steps (`[Step 1/5]`), human-readable rate-limit notes ("Backing off 5s — this is normal for popular apps") instead of HTTP codes
- **`run_pipeline()` returns a result dict** instead of just printing — exposes `success`, `generated_files`, `warnings`, `user_message`, `play_count`, `ios_count` for downstream programmatic use
- **Test fixtures** in `tests/test_small_apps.py` — unit tests (URL parsing, taxonomy loading, inheritance, tagging) and integration tests against small real apps
- **INSTALL.md** with three install paths (Claude Code, claude.ai upload, standalone CLI) and troubleshooting
- **WORKFLOW.md** with ASCII diagram of inputs → questions → pipeline → outputs and progress message examples
- **Claude Code slash command** at `.claude/commands/review-analyze.md` — invoke with `/review-analyze <url>`

### Changed

- **SKILL.md rewritten** for production-grade Claude interaction:
  - Asks at most ONE consolidated question instead of three
  - Skips question entirely when intent is clear ("full report" / "just the data")
  - Documents exactly when to ask vs. when to default
  - Returns clear partial-failure messages instead of crashes
- **App Store scraper** no longer raises on rate limits — returns partial data with a warning
- **Play Store scraper** isolates failures per locale (one locale failing doesn't kill the whole run)
- **Per-format isolation** — if one generator (e.g., PDF) fails, others still complete with a warning

### Fixed

- Apple's `503` responses no longer crash the pipeline
- Rate-limit waits respect Apple's `Retry-After` header when present
- Empty review sets handled gracefully on both stores
- Wrong app IDs return clear user messages instead of obscure errors

### Known issues

- Playwright PDF generation occasionally fails in restricted sandboxes (claude.ai's hosted environment). Workaround: use HTML format and convert externally if needed.

---

## [0.1.0] — 2026-05-14

Initial public release.

### Initial features

**Scrapers**
- Google Play Store via `google-play-scraper`
- Apple App Store via Apple's public RSS feed
- App metadata fetching for both stores
- URL parsing — paste a Play Store or App Store link, the skill extracts the ID

**Taxonomies (7 verticals)**
- `general`, `health_wellness`, `fintech`, `ecommerce`, `social`, `productivity`, `gaming`
- Auto-detection from store category via `--themes auto`
- Inheritance — vertical taxonomies extend general

**Analysis**
- Keyword-based theme tagging (default, free, reproducible)
- Optional LLM-powered tagging via Claude
- Quarterly timeline of review volume + rating mix
- 4-star "Almost-Loyal" extraction with conditional-phrase detection
- Cross-store comparison with platform-skew analysis
- Power-quote selection scored on emotional weight
- Non-English review detection

**Output formats**
- HTML × 3 (executive summary + per-store deep dives)
- PDF via Playwright
- Excel (5-sheet workbook)
- CSV (per-store + combined)
- Markdown (GitHub/Notion friendly)
- JSON (full structured analysis)

**HTML design**
- Editorial layout (Fraunces + Newsreader typography)
- Sticky masthead and navigation
- Quarterly timeline visualization
- Theme blocks with deduplicated verbatim quotes
- 4-star cards with conditional-phrase highlighting
- Cross-store comparison bars
- Searchable, filterable, paginated review archive
- CSS-variable theming for brand customization
- Fully responsive

**Documentation**
- SKILL.md (Claude entry point)
- README.md (public/GitHub)
- ETHICS.md (responsible use)
- 6 reference docs
- CONTRIBUTING.md
