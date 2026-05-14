# Installation

Three ways to install, depending on where you'll use the skill.

## Option 1 — Claude Code (slash command + skill)

For developers who use Claude Code on their machine.

```bash
# Clone into Claude Code's skills directory
git clone https://github.com/ShanShafiq01/app-review-analyzer.git \
  ~/.claude/skills/app-review-analyzer

# Run setup
cd ~/.claude/skills/app-review-analyzer
./setup.sh
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

**Note:** claude.ai runs scripts in a sandbox. The skill works because all scrapers use only Python standard library + `requests` and `google-play-scraper` (both available in the sandbox). PDF generation via Playwright doesn't work in claude.ai's sandbox — use HTML or PDF won't be in your output.

## Option 3 — Standalone CLI (no Claude)

For automation, CI pipelines, or anyone who just wants the tool without the AI layer.

```bash
git clone https://github.com/ShanShafiq01/app-review-analyzer.git
cd app-review-analyzer
./setup.sh

# Run directly
python -m scripts.run_pipeline \
  --play com.duolingo \
  --appstore 570060128 \
  --formats html,excel,csv \
  --output ./output/duolingo
```

This is the closest thing to "AppFollow without the subscription".

## Prerequisites

- **Python 3.10 or later** (the skill uses modern type hints)
- **pip** (comes with Python)
- **git** (to clone)
- Optional: **Playwright + Chromium** for PDF output
- Optional: **Anthropic API key** for LLM-powered tagging

## Manual dependency install

If `./setup.sh` doesn't fit your environment, install manually:

```bash
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

You're on a system that protects the system Python. Either:

- Use a virtual environment: `python -m venv .venv && source .venv/bin/activate && ./setup.sh`
- Use `./setup.sh --user` to install to your home directory
- Use `./setup.sh --system` to force the break-system-packages flag

### Setup hangs on `playwright install chromium`

The Chromium download is ~150MB. First-time install can take 1-2 minutes on slow connections. Wait it out.

### `Permission denied: ./setup.sh`

Make it executable: `chmod +x setup.sh && ./setup.sh`

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
# Claude Code
rm -rf ~/.claude/skills/app-review-analyzer

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
./setup.sh
```

Or download the latest release from the GitHub releases page.

Check `CHANGELOG.md` to see what changed between versions.
