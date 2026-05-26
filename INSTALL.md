# Installation

Pick the option that matches your setup. All six are first-class — no "primary" and "fallback." Each block is one self-contained copy-paste unit.

| Your situation | Go to |
|---|---|
| You use **claude.ai** in a browser (no terminal) | **Option A** |
| You use **Claude Code** (any OS) — easiest path | **Option F (plugin)** |
| You prefer git clone on a **Mac** | **Option B** |
| You prefer git clone on **Windows + PowerShell** | **Option C** |
| You prefer git clone on **Windows + Command Prompt (CMD)** | **Option D** |
| You prefer git clone on **Linux** | **Option E** |

**Python 3.10 or later** is required for Options B-F. claude.ai web (Option A) runs everything Anthropic-side — no Python needed locally.

---

## Option A — claude.ai web upload (no terminal)

For anyone using claude.ai in a browser. Zero command-line. ~60 seconds end-to-end.

1. **Download** the latest `.skill` package from [Releases](https://github.com/ShanShafiq01/app-review-analyzer/releases/latest). It's a single ~130KB file named `app-review-analyzer-vX.Y.Z.skill` (where `X.Y.Z` is the latest version number — grab whichever shows as **Latest**).

2. **Open** [claude.ai](https://claude.ai) in your browser → click your name in the bottom-left → **Settings** → **Capabilities** → **Skills**.

3. **Click** the **Upload skill** button → drop the `.skill` file into the upload area.

4. **Done.** In any chat: *"Analyze reviews for &lt;app name&gt; on both stores"* — Claude runs the skill, generates the reports, and presents them with one-click download buttons.

Why this option exists: every other option requires a terminal. This one doesn't. If you've never opened Terminal/PowerShell/CMD, choose this.

**Tradeoffs:** PDF generation doesn't work in claude.ai's sandbox (it requires Chromium). Use HTML or Excel output instead — they have all the same data plus interactive features.

---

## Option F — Claude Code plugin marketplace (zero manual steps)

For anyone using **Claude Code** on any OS — Mac, Windows, Linux. No git clone, no manual setup.

In your Claude Code session, run two commands:

```
/plugin marketplace add ShanShafiq01/app-review-analyzer
/plugin install app-review-analyzer@app-review-analyzer
```

Claude Code fetches the latest release and installs it under `~/.claude/plugins/cache/app-review-analyzer/app-review-analyzer/<version>/`. Verify with `/plugin list` — you should see `app-review-analyzer` as installed.

That's the entire install. Try it:

- *Conversational:* `Analyze reviews for Duolingo on both stores`
- *Slash command:* `/review-analyze com.duolingo`

**What happens under the hood on first invocation.** The plugin's slash command body checks for a `.venv/` inside the plugin directory. If it's missing (always true on first run), Claude runs `setup.sh` automatically — creates a venv, runs pip install for `google-play-scraper`, `pandas`, `openpyxl`, optionally Playwright + Chromium for PDF. Takes 30-60 seconds and shows a clear `"First-time setup — installing Python dependencies..."` message. Every subsequent invocation skips this and runs instantly.

This means **the user does nothing manual** — the bootstrap is fully automated via the slash command body, leveraging Claude Code's `${CLAUDE_PLUGIN_ROOT}` environment variable. Python 3.10+ still needs to be installed system-wide (the plugin can't bootstrap Python itself), but the deps are handled.

**Updating:**

```
/plugin marketplace update app-review-analyzer
```

If `requirements.txt` changed in the new version, the next `/review-analyze` invocation will detect the missing/stale venv and re-bootstrap automatically. No manual action.

**Uninstalling:**

```
/plugin uninstall app-review-analyzer@app-review-analyzer
/plugin marketplace remove app-review-analyzer
```

**Tradeoffs:** Python 3.10+ required system-wide (Mac: `brew install python@3.13`, Windows: `winget install Python.Python.3.13`, Linux: `apt install python3.13`). First invocation is slower (~30-60s) because of the dep install — subsequent invocations are normal speed. ~200MB disk usage for the venv + Chromium if PDF output is enabled.

---

## Option B — macOS (bash or zsh)

One-line install. Clones into Claude Code's skills directory and runs the setup.

```bash
git clone https://github.com/ShanShafiq01/app-review-analyzer.git ~/.claude/skills/app-review-analyzer && cd ~/.claude/skills/app-review-analyzer && ./setup.sh
```

The setup script: picks Python 3.10+ automatically, creates `.venv`, installs core deps, optionally installs Playwright (~150MB Chromium for PDF), optionally installs Anthropic SDK, runs a smoke test.

After setup, Claude Code auto-detects the skill. Try: *"Analyze reviews for &lt;app name&gt; on both stores"*.

**If Python isn't installed:** `brew install python@3.13` (or download from [python.org](https://www.python.org/downloads/macos/)). Apple Silicon Macs need the arm64/universal2 build — the installer refuses to proceed with an x86_64 Python.

---

## Option C — Windows PowerShell

```powershell
git clone https://github.com/ShanShafiq01/app-review-analyzer.git "$env:USERPROFILE\.claude\skills\app-review-analyzer"; cd "$env:USERPROFILE\.claude\skills\app-review-analyzer"; .\setup.ps1
```

**If PowerShell blocks `setup.ps1`** with "running scripts is disabled":

```powershell
# Option C1 — per-user execution policy (one-time, recommended)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Option C2 — unblock just this file (after reading it)
Unblock-File .\setup.ps1

# Option C3 — one-shot bypass
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

Or just use **Option D** (Command Prompt) instead — it bypasses PowerShell entirely.

**If Python isn't installed:** `winget install Python.Python.3.13` from a fresh PowerShell, or download from [python.org](https://www.python.org/downloads/windows/). On Windows-on-ARM, install the ARM64 build (the installer refuses to proceed with an x64 Python under emulation).

---

## Option D — Windows Command Prompt (CMD)

```cmd
git clone https://github.com/ShanShafiq01/app-review-analyzer.git "%USERPROFILE%\.claude\skills\app-review-analyzer" && cd "%USERPROFILE%\.claude\skills\app-review-analyzer" && py install.py
```

This option **bypasses PowerShell entirely** by using the `py` launcher to run `install.py` directly. No ExecutionPolicy headaches. `install.py` is the same core installer that `setup.ps1` and `setup.sh` delegate to — so the end state is identical to Options B/C/E.

**If `py` isn't found:** the Python launcher ships with every modern Windows Python install. Install Python from [python.org](https://www.python.org/downloads/windows/) and make sure "Add Python to PATH" is checked. Or use `python install.py` if `py` doesn't work.

---

## Option E — Linux

Identical to Option B — same shell, same script:

```bash
git clone https://github.com/ShanShafiq01/app-review-analyzer.git ~/.claude/skills/app-review-analyzer && cd ~/.claude/skills/app-review-analyzer && ./setup.sh
```

Listed separately so Linux users don't bounce off "macOS" headings. The installer detects Linux and adjusts: Chromium install uses `--with-deps` only if running interactively (so CI / non-TTY runs don't hang on a sudo prompt). PEP 668 detection auto-fires on Debian/Ubuntu 23.04+ — pass `--no-venv --user` if you want to install into `~/.local` instead of a venv.

**If Python isn't installed:** `sudo apt install python3.13` (Ubuntu/Debian) or your distro equivalent.

---

## Claude Code slash command

If you installed via Options B-E, the skill ships with a `.claude/commands/review-analyze.md` file that registers `/review-analyze` as a slash command in Claude Code:

```
/review-analyze https://apps.apple.com/us/app/your-app/id1234567890
```

This is a shortcut — the natural-language version (*"Analyze reviews for X"*) works exactly the same.

---

## Build the `.skill` zip yourself

If you want to upload a version that isn't published yet, or rebuild from a specific commit:

```bash
git clone https://github.com/ShanShafiq01/app-review-analyzer.git
cd app-review-analyzer
zip -r app-review-analyzer.skill . -x ".git/*" "*__pycache__*" "*.venv/*"
```

The resulting `app-review-analyzer.skill` is what you upload via Option A.

---

## After upload (Option A only)

1. In claude.ai, go to **Settings → Capabilities → Skills**.

4. The skill appears in your skills list. Use it by mentioning what it does:

   > "Analyze reviews for &lt;app name&gt; on both stores"

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

# Run directly (replace with your target app's Play package + App Store ID)
python -m scripts.run_pipeline \
  --play com.example.app \
  --appstore 1234567890 \
  --formats html,excel,csv \
  --output ./output/myapp
```

This is the closest thing to "AppFollow without the subscription".

### Non-interactive / CI install

`install.py` accepts flags so it works in CI / Dockerfiles / scripts:

```bash
python install.py --yes                                # everything (core + playwright + anthropic)
python install.py --yes --no-playwright                # skip the ~150MB Chromium fetch
python install.py --yes --no-anthropic                 # skip the anthropic SDK
python install.py --yes --no-playwright --no-anthropic # core deps only (lean)
python install.py --no-venv                            # install into the current env (no venv created)
python install.py --no-venv --user                     # pip install --user (for PEP 668 systems)
python install.py --venv .env                          # custom venv directory
```

Optional deps default to **Y** in the interactive prompts and **install** in `--yes` mode — you get full functionality (PDF output and LLM-powered tagging) out of the box. Pass `--no-playwright` / `--no-anthropic` to skip them for a lean install. Anthropic still requires `ANTHROPIC_API_KEY` at runtime to actually use `--llm-tagging`; installing the SDK alone has no side effects.

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

The pipeline checks for updates on each run (cached for 24h) and prints a one-line banner if a newer version is available. To apply an update:

### If you cloned via git (Claude Code or standalone)

**macOS / Linux:**
```bash
cd ~/.claude/skills/app-review-analyzer   # or wherever you cloned it
git pull
./setup.sh
```

**Windows (PowerShell):**
```powershell
cd $env:USERPROFILE\.claude\skills\app-review-analyzer
git pull
.\setup.ps1
```

**Any OS (portable):**
```bash
git pull
python install.py
```

The installer is idempotent — it reuses your existing `.venv` if healthy, only reinstalls deps that changed.

### If you uploaded a `.skill` zip to claude.ai

1. Download the latest `.skill` from [Releases](https://github.com/ShanShafiq01/app-review-analyzer/releases)
2. Settings → Capabilities → Skills → delete the old version
3. Click **Upload skill** and select the new zip

You won't see an in-app update notification — re-check the Releases page periodically, or follow the GitHub repo for notifications.

### Behavior changes worth knowing across versions

When pulling a new version, skim the relevant CHANGELOG entries for behavior changes. Recent examples:

- **v0.3.4** added auto-browser-open at end of pipeline (disable with `--no-open`), an in-HTML Downloads section, and the update-check banner (disable with `--no-update-check`).
- **v0.3.1** flipped the installer's optional-deps default — `--with-playwright` and `--with-anthropic` are now opt-in (was opt-out). If your CI scripts assumed Chromium would be installed automatically with `--yes`, add `--with-playwright` explicitly.

### Disabling the update-check (CI / offline use)

```bash
python -m scripts.run_pipeline ... --no-update-check
```

The check times out after 3 seconds, caches the result for 24 hours in `~/.cache/app-review-analyzer/`, and fails silently on any error (network, GitHub API rate limits, parse failures) — so it never blocks the pipeline. Disable explicitly only if you want to avoid the network call entirely.

Check `CHANGELOG.md` to see what changed between versions.
