# Security & Privacy Audit

Done before v0.2.0 public release. This document records the threat model, what was checked, what was found, and what was fixed.

## TL;DR

| Category | Verdict |
|---|---|
| Hardcoded secrets / credentials | ✅ None found |
| Shell injection / arbitrary code execution | ✅ None possible |
| Network egress | ✅ Only public store feeds (and optional Anthropic API) |
| Telemetry / phone-home | ✅ None |
| User input validation | ✅ Fixed before release |
| Output XSS / Markdown injection | ✅ Fixed before release |
| Personally identifiable information | ⚠️ Reviewer display names are kept by design — see below |

The skill scrapes only **publicly published** review data through each store's official public review feeds. Nothing is transmitted off the user's machine other than (1) requests to Apple's and Google's public review endpoints and (2) optionally, requests to the Anthropic API when `--llm-tagging` is enabled with an API key the user provides.

## Threat model

The threats considered, in priority order:

1. **The skill leaks the user's secrets** — e.g., API keys ending up in committed code, logs, or output files
2. **A malicious app ID or URL pivots into something dangerous** — path traversal, SSRF, command injection
3. **A malicious review body becomes an attack vector** — XSS in HTML output, phishing links in Markdown output, formula injection in CSV/Excel
4. **The skill scrapes more than it should** — non-public data, private endpoints, rate-limit abuse
5. **The skill phones home with usage data** — accidental telemetry or undocumented egress
6. **The skill mishandles reviewer privacy** — exposing personal data, enabling cross-platform identification, or being misused for harassment

## Checks performed

### 1. Hardcoded secrets

```bash
grep -rn -iE "(api[_-]?key|secret|token|password|bearer|sk-ant|aws_)" \
  --include="*.py" --include="*.md" --include="*.json" --include="*.sh"
```

**Result:** Zero hits on real credentials. The only matches were for keyword definitions in the taxonomy files (e.g., `"password reset"` as a complaint-theme keyword — that's data describing what users complain about, not a credential).

The `ANTHROPIC_API_KEY` is only read from `os.environ`, never hardcoded.

### 2. Shell injection / RCE

```bash
grep -rn -E "(subprocess\.|os\.system|os\.popen|shell=True|\beval\(|\bexec\()" --include="*.py"
```

**Result:** Zero hits. The skill uses no subprocess execution, no shell commands, and no `eval`/`exec` constructs in Python. The `setup.sh` script only runs `pip install` for documented dependencies — no arbitrary command execution.

### 3. URL safety / SSRF prevention

All outbound URLs are **hardcoded templates** with only the app ID and country code interpolated:

```python
RSS_URL = "https://itunes.apple.com/{country}/rss/customerreviews/page={page}/id={app_id}/sortby=mostrecent/json"
RSS_FALLBACK_URL = "https://itunes.apple.com/rss/customerreviews/page={page}/id={app_id}/sortby=mostrecent/json"
LOOKUP_URL = "https://itunes.apple.com/lookup?id={app_id}&country={country}"
```

There is no path where a user-supplied URL is fetched directly. The only HTTP destinations are:

- `itunes.apple.com` (Apple's public review feed and lookup API)
- `play.google.com` (via the `google-play-scraper` library)
- `api.anthropic.com` (only when `--llm-tagging` is set; user-controlled)
- `fonts.googleapis.com` (CSS link in HTML output, loaded by the user's browser when viewing reports, not by the skill itself)

**Fixed before release:** Earlier versions interpolated user-supplied `app_id` into URL templates without validation. While Apple and Google validate server-side (a `123/../admin` ID returns 404), this was bad hygiene. v0.2.0 adds whitelist validation in `parse_url_or_id`:

- Play Store package names must match `^[a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)+$`
- App Store IDs must match `^\d+$`

Inputs like `../etc/passwd`, `<script>`, `javascript:alert(1)`, and `123;curl evil.com` are now rejected with a clear error message before reaching any HTTP call.

### 4. Output XSS — HTML reports

All user-controlled text (review bodies, titles, reviewer names) is passed through `html.escape()` before being embedded in the HTML output. Verified by inspecting `scripts/generate_html.py` — every interpolation site uses `html.escape()`:

```python
text = html.escape(r["review"])
user = html.escape(r["user"] or "Anonymous")
title = html.escape(r["title"]) if r.get("title") else ""
```

The `<mark>` tags applied for "Almost-Loyal" conditional highlighting wrap already-escaped text, so they cannot smuggle script tags.

The HTML loads fonts from `fonts.googleapis.com` but no other external scripts or stylesheets. No `<script>` tags exist in the output beyond the small inline search/filter JavaScript that operates only on local DOM state.

### 5. Output injection — Markdown reports

**Fixed before release:** Earlier versions wrote reviewer-controlled text directly into Markdown without sanitization. This allowed reviews like `Great app! [click here](https://evil.com)` or bare URLs `Visit https://phishing.com today` to render as clickable links when an analyst published the Markdown report on GitHub or Notion.

v0.2.0 adds `_md_safe()` in `scripts/generate_markdown.py` which:

- Escapes Markdown link punctuation: `[ ] ( )` and `` ` ``
- Inserts a zero-width space after URL schemes (`http://`, `https://`, `javascript:`, `data:`, `file:`) so renderers don't auto-link them
- Preserves visual readability for humans

Tested against: bare URL phishing, `[text](url)` syntax, `javascript:` schemes, backtick code injection. All neutralized.

### 6. CSV / Excel formula injection

CSV and Excel exports include review text in cells. If a review started with `=`, `+`, `-`, or `@`, certain spreadsheet apps would interpret it as a formula, potentially calling `WEBSERVICE()` or similar.

**Current state:** The CSV/Excel generators do not currently sanitize formula-prefix characters. **This is acceptable risk for v0.2.0** because:

1. The CSV files are documented as "raw data exports" — analysts opening them understand they're raw review text
2. Modern Excel (2017+) and Google Sheets prompt before executing formulas in imported data
3. The risk is to the analyst opening the file, not to third parties, and the analyst chose to download a CSV of public reviews

Documented in `references/known_limits.md`. If a future user needs strict CSV safety (e.g., distributing CSVs broadly), prepending `'` to cells starting with `=+-@` is the standard mitigation and can be added.

### 7. Telemetry / phone-home

```bash
grep -rn -iE "(telemetry|analytics|posthog|beacon|sentry|datadog|amplitude|mixpanel|segment)" --include="*.py"
```

**Result:** Zero hits. The skill makes no analytics calls, no error reporting calls, no usage beacons.

The only network destinations are the four documented above (Apple, Google Play, Anthropic if opted in, Google Fonts when the user opens the HTML in a browser).

### 8. File-system writes

```bash
grep -rn -E "(os\.remove|shutil\.rmtree|os\.rmdir|\.unlink\()" --include="*.py"
```

**Result:** Zero hits. The skill never deletes files.

All writes go to the `--output` directory (default `./output/`). The skill does not write to system directories, the user's home directory, or any global location.

One side-effect file is always written: `_analysis.json` in the output directory, containing the full analysis data (including all review text and reviewer display names). This is documented in `WORKFLOW.md` and the `.gitignore` excludes it by default.

### 9. Dependencies

The skill depends on:

| Package | Why | Risk |
|---|---|---|
| `requests` | HTTP client | Widely audited, low risk |
| `google-play-scraper` | Play Store reviews | Third-party scraping library — review when major-version-bumping |
| `pandas` | Excel/CSV manipulation | Standard data tool |
| `openpyxl` | Excel writing | Standard |
| `playwright` (optional) | PDF generation | Pulls Chromium; trust delegated to Microsoft |
| `anthropic` (optional) | LLM tagging | Official Anthropic SDK |

No dependencies on tracking SDKs, telemetry libraries, or analytics. All are MIT/BSD/Apache-licensed.

### 10. The setup script

`setup.sh` does the following and nothing else:

1. Checks Python is installed
2. Runs `pip install` with documented packages
3. Optionally runs `playwright install chromium`
4. Optionally installs `anthropic`
5. Runs a smoke test by importing the taxonomies

No `curl | bash`. No fetching arbitrary URLs. No modifications to PATH, shell profiles, or system files.

## Privacy considerations

### What data the skill collects

All from public store endpoints:

- Review text (public — reviewer chose to publish)
- Reviewer display name (public)
- Review date and rating (public)
- App version (public)
- Country code from which the review was published (public)
- Helpful counts / vote counts (public)

### What the skill never collects

- Reviewer email addresses (the stores don't expose them)
- Reviewer location beyond country
- Cross-platform identity (the skill doesn't search outside the source store)
- Anything from the user running the skill

### What ends up on disk

In the `--output` directory:

- HTML reports — readable by anyone the user shares them with
- PDF, Excel, CSV, Markdown, JSON — same
- `_analysis.json` — internal, includes full review text and names

**Sharing reports = sharing reviewer display names.** This is by design (attribution matters) but users should be aware. ETHICS.md documents this and the SKILL.md tells Claude to surface this when appropriate.

### What goes over the network

| Destination | When | What is sent |
|---|---|---|
| `itunes.apple.com` | App Store scraping | App ID, country, page number (all from user input) |
| `play.google.com` | Play Store scraping (via library) | Package name, country, language |
| `api.anthropic.com` | Only if `--llm-tagging` set | Review text + theme list, for classification |
| `fonts.googleapis.com` | Only when user opens HTML in browser | Standard font request from browser, not the skill |

No usernames, no API keys other than the user's own Anthropic key (when opted in), no machine fingerprinting.

## What this skill **will not** be modified to do

Listed in ETHICS.md and re-stated here:

- Bypass rate limits aggressively (no high-volume scraping mode)
- Pull data from non-public sources
- Identify reviewers across platforms or against external data
- Generate fake reviews or train on review patterns to do so
- Compile lists of reviewers for retaliation or contact

Pull requests adding these features will be rejected.

## Reporting a security issue

Found something this audit missed? Please open a private security advisory on GitHub rather than a public issue, so it can be triaged before details are public.

Audit performed: **May 14, 2026**
Re-audit recommended on major version bumps, or when adding new output formats / network destinations.
