# Contributing

Thanks for considering a contribution. This is a small project with a small surface area — mostly Python scripts and JSON taxonomies. Easy to get into.

## Setup

```bash
git clone https://github.com/ShanShafiq01/app-review-analyzer.git
cd app-review-analyzer
./setup.sh
```

Then run the smoke test:

```bash
# Replace com.example.app with any real Play Store package name you want to test against
python -m scripts.run_pipeline \
  --play com.example.app \
  --countries us \
  --themes general \
  --formats html,csv \
  --output /tmp/smoke_test
```

Open `/tmp/smoke_test/playstore_deepdive.html` in a browser and confirm it renders.

## Where to contribute

**Easiest wins:**

1. **New taxonomies.** We have 7 verticals — there are at least another 10 worth covering. See `references/theme_taxonomies.md` for the format. Real estate, education, travel, dating, kids/parenting are all wanted.

2. **Better keywords for existing themes.** If you find false positives (a review getting tagged with a theme it doesn't really belong to), open an issue with the review text and the wrong tag. Even better — open a PR adjusting the keyword list.

3. **More countries.** The default country list is the four largest English-speaking storefronts. If you want to verify which countries Apple's RSS feed actually returns data for (Apple is inconsistent), that's a useful PR.

**Medium effort:**

4. **Multilingual support.** Currently the skill detects non-English reviews and excludes them from theme tagging. A real solution would either translate-then-tag or train language-specific keyword sets. The LLM tagger could handle this if pointed at it.

5. **Sentiment scoring per theme.** Right now we count theme mentions. A theme appearing 20 times might be 15 angry mentions and 5 calm ones — knowing that would help.

6. **Performance.** The Play Store scraper is slow for popular apps (large apps with hundreds of thousands of reviews can take 3+ minutes). Better deduplication, less redundant querying, or caching across runs would help.

**Bigger projects:**

7. **Historical trend tracking.** Run the analysis weekly, store the results, generate "this changed since last month" reports.

8. **Cross-app competitive comparison.** Compare three apps in the same category in one report.

9. **White-label templates.** Multiple report design templates, not just the editorial one.

## Pull request guidelines

- One change per PR. If you fix a bug and add a feature, that's two PRs.
- Update tests if behavior changes. Currently we have minimal tests — adding them is also a contribution.
- Update the README if you add a CLI flag or change a default.
- Update the CHANGELOG under an `[Unreleased]` section.
- Match the existing code style. We're not picky — just be consistent with what's there.

## Code style

- Python 3.10+ features OK (`X | None`, structural pattern matching, etc.)
- Type hints encouraged but not required
- Imports inside functions are OK when they're heavy or optional dependencies
- Strings: double quotes for user-facing text, single quotes for internal/structural
- Line length: don't sweat it, but don't make a 200-char monster

## Adding a new taxonomy

This is the most useful kind of contribution and the easiest. See `references/theme_taxonomies.md` for the schema. The short version:

1. Copy `templates/themes/general.json` to `templates/themes/your_vertical.json`
2. Set `name`, `label`, `description`, and `extends: "general"`
3. Add 5–10 vertical-specific negative themes with 8–20 keywords each
4. Add 3–5 vertical-specific positive themes
5. Run the smoke test on a known app in your vertical and check the tag distribution looks right
6. Open a PR

## Reporting bugs

Use GitHub Issues. Include:

- The CLI command you ran (or the prompt you gave Claude)
- The Python version (`python --version`)
- The full stack trace if there was a crash
- Whether you have `ANTHROPIC_API_KEY` set (for LLM tagging issues)

## Reporting bad theme tags

Especially valuable. Format:

```
Review text: "I love the design but the camera always crashes when I open the app"
Wrong tag: design_quality (positive)
Why: The review is overall negative — the praise is qualified by "but"
Suggested fix: Add "but X crashes" / "but X always Y" patterns to a "qualified praise" filter
```

The taxonomies will only improve through real-world examples. Send them.

## Code of conduct

Be kind. Don't use the project to harm app developers. See ETHICS.md.

Maintainer reserves the right to decline contributions that lower quality, add unnecessary complexity, or push the project toward uses out of scope per ETHICS.md.
