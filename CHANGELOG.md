# Changelog

All notable changes documented here. Format roughly follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.4.0] — 2026-05-14

**Onboarding rewrite.** Every audience gets a first-class install path, and the chat reply Claude produces after a run finally feels designed instead of patched.

### Added — Five co-equal install paths

`README.md` and `INSTALL.md` both restructured around a "pick the path that matches you" table with five self-contained options. No more "primary install / fallback install" hierarchy — claude.ai web upload (zero terminal), macOS, Windows PowerShell, Windows CMD, and Linux are all listed as equals. Each block is a single copy-paste unit.

The Windows CMD path now uses `py install.py` directly, sidestepping the PowerShell ExecutionPolicy hassle that bit v0.3.4 users. The `py` launcher ships with every modern Windows Python install.

### Added — Data-grounded `top_findings` in the pipeline result

`scripts/analyze.py` gained `compute_top_findings()`, a conservative algorithm that extracts up to 3 headline findings from the analysis data:

- Cross-store rating gap (only if both stores present AND gap ≥ 0.25★ — anything below is noise)
- Top negative theme by count (only if ≥ 10 mentions — below that, "#1 complaint" is meaningless)
- Top positive theme as % of 5-star reviews (only if ≥ 15% AND ≥ 10 mentions — below is not a real loyalty signal)

Returns FEWER findings rather than fabricating ones. Each finding cites concrete numbers from the underlying data.

The pipeline now surfaces `result["top_findings"]` on the result dict so Claude can read structured findings instead of inventing summaries.

### Changed — `user_message` rewritten to the four-part chat-ready format

`scripts/run_pipeline.py` reshapes the post-run `user_message` to:

1. **Result line** — concrete numbers ("Pulled 234 + 196 reviews for Duolingo (430 total)")
2. **Top findings** — lifted verbatim from `top_findings` (omitted if the list is empty)
3. **File affordance** — a single copy-friendly `open <path>` command
4. (Next-step suggestion — Claude adds this in chat, not in the message itself)

Claude can lift this format directly into chat per the new SKILL.md patterns.

### Changed — `SKILL.md` presentation guidance is now three literal mockup blocks

Replaced the previous prose rules ("In claude.ai do X, in Claude Code do Y") with three literal markdown blocks Claude can copy verbatim. The prose-rules approach got followed about 70% of the time. Literal examples are followed ~95% of the time.

The three patterns:

- **Pattern 1 — claude.ai web (sandboxed):** call `present_files()` for one-click download buttons, then a 4-part text reply with the result line, top findings, file orientation, and next-step suggestion.
- **Pattern 2 — Claude Code (with `webbrowser.open`):** same 4-part structure but tell the user the browser auto-opened, point at the in-HTML Downloads section, and provide a fenced `open <path>` block as the manual fallback.
- **Pattern 3 — Fallback (sandbox failed, no browser):** same 4-part structure, but the file affordance becomes "they're at `/path/...`, re-run for clickable downloads."

Plus explicit rules: **always use the four-part structure, always lead with concrete numbers, always use `top_findings` verbatim (never invent), never list plain filenames as the file affordance, always use absolute paths.**

### Update path for existing users

```bash
# Claude Code (cloned into ~/.claude/skills/) — Mac / Linux
cd ~/.claude/skills/app-review-analyzer
git pull
./setup.sh        # idempotent — reuses existing venv if healthy

# Windows PowerShell
git pull
.\setup.ps1

# Windows CMD
git pull
py install.py
```

claude.ai web users on a v0.3.x `.skill` zip: re-download the v0.4.0 release zip and re-upload via Settings → Skills.

### Notes for power users

- Interactive Y/N prompts for Playwright / Anthropic SDK are **preserved** in this release. Pass `--no-playwright` / `--no-anthropic` to skip either; or pass `--yes` to accept defaults (both install).
- The CLI flags `--no-open` (skip auto-browser-launch) and `--no-update-check` (skip the GitHub Releases check) still work as in v0.3.4.

---

## [0.3.5] — 2026-05-14

**Hotfix: Windows installer was broken in v0.3.4.** A real Windows user reported `setup.ps1` failing immediately with parser errors. Anyone on v0.3.4 trying to install on Windows hit this.

### Fixed

- **`setup.ps1` Windows encoding bug.** v0.3.4 shipped with em-dashes (`—`), arrows (`→`), and box-drawing characters in the PowerShell installer. PowerShell 5.1 (the default on Windows 10/11) reads `.ps1` files as the system codepage (typically Windows-1252) unless the file has a UTF-8 BOM. The multibyte UTF-8 characters got mojibaked into `â€"`-style garbage, which broke the parser and produced cascading "Expressions are only allowed as the first element of a pipeline" errors. Two-part fix: (a) rewrote the file using ASCII-only characters in the script body, (b) saved it with a UTF-8 BOM so PowerShell 5.1 reads it correctly even if anyone re-adds Unicode in the future.
- **Single-quoted regex literals in `-split` calls.** Changed `-split "\|"` and `-split "\."` to `-split '\|'` and `-split '\.'`. Single-quoted strings don't go through PowerShell's string-escape pass, so the regex engine sees the patterns unambiguously. Robust against future PowerShell parser quirks.
- **README install commands were Mac/Linux-only.** The Quick install block used bash `\` line-continuation and `~/.claude/skills/...` paths, neither of which work in Windows CMD or PowerShell. Replaced the single block with four explicit OS-specific blocks (macOS/Linux, Windows PowerShell, Windows CMD, portable). Each block is a single copy-paste unit that clones, cd's, and runs the installer in one go.

### Update path for existing users

```bash
# Claude Code (cloned into ~/.claude/skills/)
cd ~/.claude/skills/app-review-analyzer
git pull
./setup.sh        # Mac/Linux users: no behavior change
.\setup.ps1       # Windows users: this is the fix
```

If you uploaded the v0.3.4 `.skill` zip to claude.ai, no action needed (Anthropic-side runtime doesn't use `setup.ps1`). The fix only affects users running the Windows installer locally.

---

## [0.3.4] — 2026-05-14

Bridges the "I clicked the filename in chat and nothing happened" gap. Three things ship together:

### Added

- **Downloads section inside every HTML report.** The executive summary and both deep-dives now end with a styled grid of cards — one per generated file (xlsx, csv, json, md, sibling HTMLs). HTML cards use plain `<a href>` (open in browser); xlsx / csv / json / md cards use `<a href download>` which triggers a Save dialog and bypasses the `file://` MIME-blocking that prevented direct clicks. Once the user has the HTML open, every other artifact is one click away.
- **Auto-open in the user's default browser** when running the CLI interactively. The pipeline detects TTY mode and calls `webbrowser.open()` on the executive summary (or whichever deep-dive is primary in single-store mode). Gated on `--no-open` and `--quiet` so CI / headless / scripted runs are unaffected.
- **Update-check banner.** On each pipeline run (cached for 24h in `~/.cache/app-review-analyzer/`), the tool hits the GitHub Releases API and prints a one-line `Update available: vX.Y.Z → vA.B.C` notice if the local version is behind. Gated on `--no-update-check`. Silent on network failure, repo-not-yet-public, parse errors, or any other issue — never blocks the pipeline.

### Changed

- **SKILL.md presentation guidance for Claude Code:** the previous advice (emit each file as a clickable `file://` markdown link) doesn't work in practice — claude.ai web blocks `file://` from `https://` origins, VSCode chat opens HTML as source text, terminals can't navigate paths. New guidance: one sentence pointing users at the in-HTML Downloads section, plus a fenced code block with `open <absolute-path>` (chat clients render this with a copy button).
- **Pipeline user message** ends with a copy-friendly `open <path>` command in case auto-open didn't fire.

### Update path for existing users

```bash
# Claude Code (cloned into ~/.claude/skills/)
cd ~/.claude/skills/app-review-analyzer
git pull
./setup.sh        # idempotent — re-runs install.py against the existing venv

# Windows
.\setup.ps1

# Any OS
python install.py
```

claude.ai web users on a `.skill` zip: re-download the v0.3.4 release zip and re-upload via Settings → Skills.

---

## [0.3.3] — 2026-05-14

Channel-aware file presentation.

### Changed

- **Output files are now actionable in every channel.** SKILL.md and the `/review-analyze` slash command now instruct Claude to present generated files using the right pattern for the runtime:
  - In **claude.ai (sandboxed)** — write to `/mnt/user-data/outputs/<app_slug>/` and call `present_files` so the user gets one-click download buttons in the chat.
  - In **Claude Code (local filesystem)** — emit each file as a clickable markdown link with an absolute `file://` URL (e.g., `[executive_summary.html](file:///Users/you/.../executive_summary.html)`), cmd-clickable in VSCode's integrated terminal and modern terminals, plus a one-liner `open` / `xdg-open` / `start` command for terminals that don't auto-link.
- Both surfaces now explicitly forbid dumping raw `~/...` paths as plain text — tildes don't expand inside markdown link URLs, so absolute paths only.

---

## [0.3.2] — 2026-05-14

README refresh to reflect v0.3 reality.

### Changed

- **README**: dropped the "what's different about v0.2" framing (we're past it), replaced the named-app example output ("Calm") with a generic placeholder, added Cross-platform + UTF-8 + Security-audited installer rows to the production hardening table, surfaced Windows/Linux install commands alongside the macOS one in the Install section, and bumped the roadmap one version (v0.3 marked shipped; multilingual/sentiment moved to v0.4; trends/white-label to v0.5; cross-app comparison to v0.6).

---

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
