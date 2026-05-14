# Changelog

All notable changes documented here. Format roughly follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.3.1] — 2026-05-14

Polish release on top of v0.3.0.

### Changed

- **Generic example placeholders throughout user-facing docs.** Installer output, README, INSTALL.md, slash command examples, run_pipeline help text, WORKFLOW.md URL parsing examples, and references/* worked examples now use `com.example.app` / `1234567890` / "Your App" placeholders instead of naming a specific real-world app. Sidesteps any "is this app endorsed by us?" misperception when readers scan the repo for the first time. CHANGELOG.md is unchanged — it remains a factual record of what was tested.
- **Optional dependencies install by default.** Playwright (PDF output) and the Anthropic SDK (LLM-powered tagging) both default to `Y` in the interactive prompts and to **install** in `--yes` mode. Reflects that this skill ships all features and most users will want them. Pass `--no-playwright` / `--no-anthropic` for a lean install. Anthropic still requires `ANTHROPIC_API_KEY` at runtime to actually use `--llm-tagging` — installing the SDK alone has no side effects.

### Added

- `--no-anthropic` flag on `install.py` for symmetry with `--no-playwright`.

---

## [0.3.0] — 2026-05-14

Cross-platform release. The skill now works on Windows and Linux, not just macOS.

### Added

- **Windows support.** New `setup.ps1` PowerShell installer picks a usable Python via the `py` launcher and delegates to `install.py`. Refuses x86/x64 Python on Windows-on-ARM hosts to prevent the same broken-toolchain failure mode the Apple Silicon check already prevents.
- **Portable `install.py`.** Pure-Python installer that works on Windows, macOS, and Linux. Handles venv creation with health-check (refuses to reuse a broken `.venv/` left behind by an older Python), PEP 668 externally-managed Pythons (Debian, Homebrew) via `--user` flag, and skips `playwright install --with-deps` on non-Linux or non-interactive shells to avoid hangs on sudo prompts. Accepts `--yes`, `--no-venv`, `--with-anthropic`, `--no-playwright`, `--user`, and `--venv DIR` flags for CI use.
- **Trust & supply chain section in INSTALL.md.** Documents what the installer downloads and trusts: four pinned core deps from PyPI, opt-in Playwright Chromium binary from Microsoft's CDN, and an explicit guarantee that nothing runs `curl | bash`, modifies shell profiles, or installs system-wide without consent.

### Changed

- **All 15 file I/O sites now declare `encoding="utf-8"`.** Previously every `Path.read_text()` / `write_text()` call relied on the platform default, which is `cp1252` on Windows — and would have raised `UnicodeDecodeError` on the first French, Japanese, German, or emoji-bearing review. Verified end-to-end on 1,500 real Duolingo reviews from FR/JP/DE: 1,333 contained non-ASCII text, all round-tripped correctly through every output format (HTML, CSV, Markdown, JSON).
- **`run_pipeline.py` reconfigures stdout/stderr to UTF-8** at module load so `print()` of non-ASCII review text doesn't fail under `LC_ALL=C` or minimal-container locales.
- **`setup.sh` rewritten as a thin wrapper around `install.py`.** Auto-picks Python 3.10+ matching the host architecture, refuses x86_64 Python on Apple Silicon (which was the actual blocker on the author's machine — pandas/numpy source builds failed because the linker couldn't bridge x86_64 to arm64), then delegates to install.py so install logic lives in one place.
- **`requirements.txt` is the single source of truth for dependency versions.** `install.py` parses it at runtime. Playwright pinned to `>=1.40,<2.0` to bound which Chromium revision the optional install fetches.

### Tested

- macOS arm64 (Python 3.13): full pipeline end-to-end against Duolingo App Store FR/JP/DE — `appstore_deepdive.html` (106,133 non-ASCII chars), `all_reviews.csv` (52,592), `summary.md`, `_analysis.json` — all valid UTF-8, characters preserved.
- All 12 fast unit + security tests pass post-fix.
- Audited by three independent reviewers (code review, security, evidence-based reality check) before commit. Critical bug caught: `setup.ps1` was clobbering PowerShell's automatic `$args` variable — fixed by using `param([Parameter(ValueFromRemainingArguments=$true)]$UserArgs)`.

### Honest scope of testing

Linux and Windows have been code-reviewed and structurally portable but not executed. The `install.py` Windows path handles `Scripts\python.exe` and the PEP 668 detection covers Debian/Homebrew, but neither has been run on a real machine yet. File issues if you hit problems.

---

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
