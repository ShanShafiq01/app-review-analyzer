# Installation

Three ways to install, depending on where you'll use the skill.

## Platform support

| Platform | Recommended installer | Notes |
|---|---|---|
| macOS / Linux | `./setup.sh` | Picks Python 3.10+ automatically, creates `.venv` |
| Windows (PowerShell) | `.\setup.ps1` | Same logic, picks Python via the `py` launcher |
| Any OS (portable) | `python install.py` | Pure-Python installer — works everywhere |
| claude.ai web | Upload `.skill` file | No local install needed; Anthropic runs the code |

**Python 3.10 or later** is required on all platforms (the code uses modern type hints and string features).

## Option 1 — Claude Code (slash command + skill)

For developers who use Claude Code on their machine.

```bash
# Clone into Claude Code's skills directory
git clone https://github.com/ShanShafiq01/app-review-analyzer.git \
  ~/.claude/skills/app-review-analyzer

# Run setup (macOS / Linux)
cd ~/.claude/skills/app-review-analyzer
./setup.sh
```

Windows (PowerShell):

```powershell
git clone https://github.com/ShanShafiq01/app-review-analyzer.git `
  $env:USERPROFILE\.claude\skills\app-review-analyzer

cd $env:USERPROFILE\.claude\skills\app-review-analyzer
.\setup.ps1
```

If PowerShell refuses to run the script (default execution policy blocks unsigned scripts), in order of recommendation:

```powershell
# Safest — unblock just this file after reading it
Unblock-File .\setup.ps1
.\setup.ps1

# Per-user execution policy (one-time, allows local scripts)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\setup.ps1

# One-shot bypass — only use after reading the script you're about to run
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

Or skip the wrapper entirely:

```powershell
python install.py
```

The setup script:
- Installs Python dependencies
- Optionally installs Playwright + Chromium for PDF generation
- Optionally installs the Anthropic SDK for LLM-powered tagging
- Runs a smoke test

After setup, Claude Code automatically picks up the skill. Try:

```
You: Analyze reviews for Calm on both stores
Claude: [Claude reads SKILL.md, asks one question about formats, runs the pipeline]
```

### Optional — Claude Code slash command

The skill ships with a `.claude/commands/review-analyze.md` file that registers `/review-analyze` as a slash command in Claude Code:

```
/review-analyze https://apps.apple.com/us/app/calm/id571800810
```

This is a shortcut — the natural language version works exactly the same.

## Option 2 — Claude.ai (manual upload)

For users on claude.ai (the web/mobile interface).

1. Download the latest `.skill` package from [Releases](https://github.com/ShanShafiq01/app-review-analyzer/releases) — or build it yourself:

   ```bash
   git clone https://github.com/ShanShafiq01/app-review-analyzer.git
   cd app-review-analyzer
   zip -r app-review-analyzer.skill . -x ".git/*" "*__pycache__*"
   ```

2. In claude.ai, go to **Settings → Capabilities → Skills**

3. Click **Upload skill** and select the `.skill` file

4. The skill appears in your skills list. Use it by mentioning what it does:

   > "Analyze reviews for Duolingo on both stores"

**Note:** claude.ai runs scripts in a sandbox. The skill works because all scrapers use only Python standard library + `requests` and `google-play-scraper` (both available in the sandbox). PDF generation via Playwright doesn't work in claude.ai's sandbox — use HTML, or PDF won't be in your output.

## Option 3 — Standalone CLI (no Claude)

For automation, CI pipelines, or anyone who just wants the tool without the AI layer.

```bash
git clone https://github.com/ShanShafiq01/app-review-analyzer.git
cd app-review-analyzer

# Any OS — portable Python installer
python install.py

# Or the OS-specific wrappers:
./setup.sh       # macOS / Linux
.\setup.ps1      # Windows PowerShell

# Run directly
python -m scripts.run_pipeline \
  --play com.duolingo \
  --appstore 570060128 \
  --formats html,excel,csv \
  --output ./output/duolingo
```

This is the closest thing to "AppFollow without the subscription".

### Non-interactive / CI install

`install.py` accepts flags so it works in CI / Dockerfiles / scripts:

```bash
python install.py --yes                  # accept all defaults, install playwright
python install.py --yes --no-playwright  # skip Chromium download (smaller)
python install.py --yes --with-anthropic # also install LLM tagging SDK
python install.py --no-venv              # install into the current env (no venv created)
python install.py --no-venv --user       # pip install --user (for PEP 668 systems without a venv)
python install.py --venv .env            # custom venv directory
```

## Prerequisites

- **Python 3.10 or later** (the skill uses modern type hints)
- **pip** (comes with Python)
- **git** (to clone)
- Optional: **Playwright + Chromium** for PDF output
- Optional: **Anthropic API key** for LLM-powered tagging

### Apple Silicon (M1/M2/M3) note
You need a native **arm64** Python — not an x86_64 Python under Rosetta. Confirm with:

```bash
python3 -c "import platform; print(platform.machine())"   # should print: arm64
```

If it prints `x86_64`, install the universal2 Python from python.org or `brew install python@3.13`. `setup.sh` and `install.py` both refuse to proceed on a mismatched arch — they fail fast rather than letting pandas/numpy fail mid-build.

### Windows note
The default `python` in CMD after a python.org install usually works. If your system has multiple Pythons, use the `py` launcher:
```powershell
py -3.13 install.py
```

On **Windows-on-ARM** (Surface Pro X, Volterra, etc.), make sure you install the **ARM64** build of Python from python.org — not the x64 one. `setup.ps1` and `install.py` both refuse to proceed if they detect an x86/x64 Python on an ARM64 host, for the same reason as the Apple Silicon check above.

## Trust & supply chain notes

What the installer trusts and downloads, so you can decide if you're comfortable running it:

- **Four core dependencies** from PyPI: `google-play-scraper`, `requests`, `pandas`, `openpyxl`. Version floors are pinned in `requirements.txt`; you get whatever PyPI serves above those floors at install time.
- **Playwright (optional, opt-in)**: installing this triggers a separate `playwright install chromium` step, which downloads a ~150MB Chromium binary from Microsoft's CDN (`playwright.azureedge.net`). The Playwright Python package version is pinned to `>=1.40,<2.0` in `requirements.txt` — that bounds which Chromium revision is fetched.
- **Anthropic SDK (optional, opt-in)**: only if you pass `--with-anthropic` or answer yes to the prompt. Required for `--llm-tagging`.
- The installer **never** runs `curl | bash`, never modifies your shell profile, never installs system-wide packages without your consent (`--no-venv` requires you to opt in explicitly, and refuses on PEP 668 systems unless you also pass `--user`).

If you want a fully air-gapped install, run `pip install -r requirements.txt` manually inside a venv you create yourself, and skip the optional Playwright Chromium fetch.

## Manual dependency install

If neither `setup.sh` / `setup.ps1` / `install.py` fits, install manually:

```bash
# Create a venv (recommended)
python -m venv .venv
source .venv/bin/activate           # macOS / Linux
# .venv\Scripts\Activate.ps1        # Windows PowerShell

pip install --upgrade pip
pip install google-play-scraper requests pandas openpyxl

# Optional
pip install playwright && playwright install chromium
pip install anthropic
```

Then verify:

```bash
python -m scripts.run_pipeline --help
```

## Troubleshooting

### `ModuleNotFoundError: No module named 'google_play_scraper'`

Run `./setup.sh` again, or `pip install google-play-scraper` manually.

### `playwright: command not found`

Playwright wasn't installed. Either skip PDF output (remove `pdf` from `--formats`) or:

```bash
pip install playwright
playwright install chromium
```

### Setup fails on `pip install --break-system-packages` rejection

You're on a system that protects the system Python (Debian/Ubuntu, recent macOS, etc.). All three installers (`setup.sh`, `setup.ps1`, `install.py`) handle this by creating a `.venv/` by default — you should never hit the `--break-system-packages` path unless you pass `--no-venv` to `install.py`.

### Setup hangs on `playwright install chromium`

The Chromium download is ~150MB. First-time install can take 1-2 minutes on slow connections. Wait it out.

### `Permission denied: ./setup.sh`

Make it executable: `chmod +x setup.sh && ./setup.sh`

### Windows: "running scripts is disabled on this system"

PowerShell's default execution policy blocks unsigned scripts. Either run with bypass:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

…or enable scripts for your user:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

…or skip the wrapper entirely and run `python install.py` directly.

### Mac: "Broken toolchain: cannot link a simple C program"

You're running an x86_64 Python on Apple Silicon. The pandas/numpy build can't link arm64 binaries from an x86_64 toolchain. Fix: install a native arm64 Python (`brew install python@3.13` or python.org universal2 installer). `setup.sh` detects this and refuses to proceed, so you shouldn't hit this with the v0.3+ installer.

### Skill not appearing in Claude Code

- Confirm `~/.claude/skills/app-review-analyzer/SKILL.md` exists
- Restart Claude Code (the skills directory is scanned on launch)
- Run `claude skills list` to see what Claude Code sees

### Skill not appearing in claude.ai after upload

- The `.skill` file must be a valid ZIP
- The SKILL.md must have proper YAML frontmatter with `name` and `description`
- Wait a few seconds after upload — the indexing takes a moment

## Uninstall

```bash
# Claude Code — macOS / Linux
rm -rf ~/.claude/skills/app-review-analyzer

# Claude Code — Windows PowerShell
Remove-Item -Recurse -Force $env:USERPROFILE\.claude\skills\app-review-analyzer

# claude.ai
Settings → Capabilities → Skills → Delete

# Standalone
rm -rf app-review-analyzer
```

The skill writes no files outside its own directory, so removal is clean.

## Updating

```bash
cd ~/.claude/skills/app-review-analyzer
git pull
./setup.sh        # or  .\setup.ps1  on Windows  /  python install.py  anywhere
```

Or download the latest release from the GitHub releases page.

Check `CHANGELOG.md` to see what changed between versions.
