# Examples

Fully-worked invocations from start to finish. Run any of these and you'll get a complete report bundle.

## 1. Most common case — both stores, default formats

```bash
python -m scripts.run_pipeline \
  --play com.example.app \
  --appstore 1234567890 \
  --countries us,gb,ca,au \
  --themes general \
  --formats html,excel,csv \
  --output ./output/myapp \
  --app-display-name "Your App"
```

Generates:
- `executive_summary.html`
- `playstore_deepdive.html`
- `appstore_deepdive.html`
- `myapp_reviews.xlsx`
- `playstore_reviews.csv`, `appstore_reviews.csv`, `all_reviews.csv`

Time: 2-4 minutes for apps with large review counts.

## 2. Health app with vertical-specific taxonomy

```bash
python -m scripts.run_pipeline \
  --play com.calm.android \
  --appstore 571800810 \
  --themes health_wellness \
  --formats html,pdf,excel \
  --output ./output/calm \
  --app-display-name "Calm"
```

The `health_wellness` taxonomy adds themes like `tracking_accuracy`, `mental_health`, `habit_formed`, `doctor_validated` on top of the general themes.

## 3. Auto-detect taxonomy from store category

```bash
python -m scripts.run_pipeline \
  --play com.spotify.music \
  --appstore 324684580 \
  --themes auto \
  --formats html \
  --output ./output/spotify
```

The skill reads the app's store category and picks an appropriate taxonomy. Spotify → category "Music" → falls back to `general` (no music-specific taxonomy yet).

## 4. URL inputs (paste directly from your browser)

```bash
python -m scripts.run_pipeline \
  --play "https://play.google.com/store/apps/details?id=com.proov" \
  --appstore "https://apps.apple.com/us/app/proov/id1574349479" \
  --themes health_wellness \
  --formats html,pdf,excel,csv,markdown \
  --output ./output/proov \
  --app-display-name "Proov Fertility"
```

The skill extracts `com.proov` and `1574349479` from the URLs.

## 5. Single store only (app isn't on the App Store)

```bash
python -m scripts.run_pipeline \
  --play com.some.android.only.app \
  --themes general \
  --formats html,excel \
  --output ./output/android_only
```

No executive summary is generated (no cross-store data). The deep-dive is the headline document.

## 6. Custom branding for a client deliverable

```bash
python -m scripts.run_pipeline \
  --play com.client.app \
  --appstore 123456789 \
  --themes ecommerce \
  --formats html,pdf \
  --output ./output/client_project \
  --app-display-name "Client App" \
  --byline "Prepared by [Your Agency] · May 2026"
```

The `--byline` adds a credit line to every report footer. For deeper rebranding (changing colors), edit the CSS in `scripts/generate_html.py` and re-run.

## 7. LLM-powered tagging (higher accuracy)

```bash
export ANTHROPIC_API_KEY="sk-ant-..."

python -m scripts.run_pipeline \
  --play com.example \
  --appstore 999999 \
  --themes general \
  --llm-tagging \
  --formats html,excel \
  --output ./output/example_llm
```

Costs ~$0.10–$0.30 per analysis. Use when keyword false positives are unacceptable.

## 8. Quick markdown summary only

```bash
python -m scripts.run_pipeline \
  --play com.notion.id \
  --themes productivity \
  --formats markdown \
  --output ./output/notion
```

Just the `summary.md`. Good for piping into another tool or pasting into a Notion page.

## 9. Quiet mode for CI/automation

```bash
python -m scripts.run_pipeline \
  --play com.example \
  --formats json \
  --output ./output/ci \
  --quiet
```

No stderr output. Just produces `full_analysis.json` for downstream processing.

## 10. Multi-country for a global app

```bash
python -m scripts.run_pipeline \
  --play com.whatsapp \
  --appstore 310633997 \
  --countries us,gb,ca,au,nz,ie,in,za,sg,ph \
  --themes social \
  --formats html,excel \
  --output ./output/whatsapp
```

Each country adds up to ~500 App Store reviews. Watch out for non-English reviews — they'll be flagged in the data but skipped from thematic analysis.

## Using in Claude (conversational)

If you're in Claude.ai or Claude Code with this skill installed, you don't run any of the above directly. You just talk:

```
You:    Analyze reviews for Calm on both stores
Claude: (reads SKILL.md, finds the app IDs, asks one question about format
         preferences, then runs the pipeline and presents the output)
```

Other natural triggers Claude recognizes:

- "What are users saying about [app]?"
- "Pull reviews for [URL]"
- "Compare reviews of [app A] and [app B]" (runs the pipeline twice and compares)
- "Generate a review audit for [app]"
- "I'm doing competitive research on [app]"

Claude will:

1. Identify the app from URL or name
2. Confirm the scope (formats, countries) — defaults are sensible
3. Run the pipeline
4. Present the generated files
5. Highlight the most interesting findings in chat

## Inspecting the JSON output

```bash
# Top-level keys
python -c "import json; d=json.load(open('./output/myapp/full_analysis.json')); print(list(d.keys()))"

# Theme counts on Play Store
python -c "
import json
d = json.load(open('./output/myapp/full_analysis.json'))
for k, v in sorted(d['play']['neg_counts'].items(), key=lambda x: -x[1])[:5]:
    print(f'{v:4d}  {k}')
"
```

## Re-running and updating

The skill always overwrites the files in `--output`. To preserve a previous run:

```bash
# Run 1 — save the snapshot
python -m scripts.run_pipeline ... --output ./output/calm_2026_may
cp ./output/calm_2026_may/full_analysis.json ./snapshots/calm_2026_may.json

# Run 2 — fresh analysis later
python -m scripts.run_pipeline ... --output ./output/calm_2026_aug
cp ./output/calm_2026_aug/full_analysis.json ./snapshots/calm_2026_aug.json

# Then write your own diff script to compare snapshots
```

## Troubleshooting

**"No reviews found"** — usually one of:
- Wrong app ID (double-check the URL)
- App removed from store
- App in store but with reviews disabled
- Apple's RSS having a bad moment (try again in 30 minutes)

**"Module not found: google_play_scraper"** — run `./setup.sh` again or `pip install google-play-scraper`.

**"playwright not installed"** — PDF generation skipped, HTML still works. Run `pip install playwright && playwright install chromium` if you need PDFs.

**Pipeline hangs** — usually the Play Store scraper on a very popular app. Wait a few minutes. If truly stuck, Ctrl+C and re-run with a smaller `--countries` list.

**"Got 0 App Store reviews"** — Apple is rate-limiting you. Wait an hour and retry.
