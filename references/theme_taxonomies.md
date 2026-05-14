# Theme Taxonomies

Taxonomies are JSON files in `templates/themes/` that define what to look for in reviews. Picking the right one is the single biggest determinant of how useful the analysis is.

## The seven shipped taxonomies

| Name | Best for | Example apps |
|---|---|---|
| `general` | Any app — sensible fallback | Generic utility apps |
| `health_wellness` | Fertility, meditation, fitness, mental health, nutrition, sleep | Calm, MyFitnessPal, Proov, Headspace |
| `fintech` | Banking, investing, crypto, payments, budgeting | Robinhood, Cash App, Mint, Coinbase |
| `ecommerce` | Shopping, marketplaces, delivery, classifieds | Amazon, Etsy, DoorDash, eBay |
| `social` | Messaging, social media, dating, community | Discord, Bumble, Reddit, WhatsApp |
| `productivity` | Notes, calendar, task management, work tools | Notion, Todoist, Slack, Things |
| `gaming` | Mobile games of all genres | Clash Royale, Genshin Impact, Candy Crush |

## Auto-detection

`--themes auto` uses the app's store category to pick:

| Store category | Taxonomy chosen |
|---|---|
| Health & Fitness, Medical, Lifestyle | health_wellness |
| Finance | fintech |
| Shopping, Food & Drink | ecommerce |
| Social Networking, Communication, Dating | social |
| Productivity, Business, Utilities | productivity |
| Games (any subcategory) | gaming |
| Everything else | general |

If you disagree with the auto-pick, just specify directly: `--themes fintech`.

## Inheritance

All vertical taxonomies inherit from `general` via the `extends` field. So when you pick `health_wellness`, you get:

- All 12 negative themes from `general` (crashes, login, UX, pricing, support, etc.)
- **Plus** 6 health-specific themes (tracking accuracy, data loss, medical concerns, etc.)

This way, a fertility app review that says "the app crashes" still gets tagged with `crashes_bugs` from the general taxonomy.

The inheritance is one level deep. You can't `extend` a vertical that itself extends another.

## Schema

```json
{
  "name": "your_vertical",
  "label": "Your Vertical (Human Readable)",
  "description": "When to use this taxonomy.",
  "version": "1.0",
  "extends": "general",
  "negative_themes": {
    "theme_key_one": {
      "label": "Theme label shown in reports",
      "keywords": ["keyword 1", "keyword 2", "phrase to match", "another phrase"]
    },
    "theme_key_two": {
      "label": "Another theme",
      "keywords": ["..."]
    }
  },
  "positive_themes": {
    "positive_key": {
      "label": "Positive theme label",
      "keywords": ["..."]
    }
  }
}
```

## Writing keywords that work

The keyword matcher is **case-insensitive substring**. A keyword `"crash"` matches `Crash`, `crashes`, `crashed`, `crashing`. But it also matches `crashed into Tucker Carlson's website` (if that ever shows up in a review).

Good keywords are:

- **Specific**: `"won't let me log in"` is better than `"problem"`
- **Phrases over single words**: `"asks for too much information"` is better than `"info"`
- **Common spellings**: include both `"can't"` and `"cant"` — users skip apostrophes
- **Idiomatic**: `"rip off"`, `"waste of money"`, `"life saver"` — natural review language, not technical terms

Bad keywords are:

- Too generic: `"bad"` matches `"bad day"`, `"bad weather"`, even praise like `"isn't bad at all"`
- Too specific: `"crashes when I open the navigation drawer on Pixel 7"` — too narrow to match
- Negations that flip: `"slow"` will match `"isn't slow"`, `"never slow"`. The skill doesn't do negation handling.

## Adding a new taxonomy

```bash
# 1. Copy general.json as a starting point
cp templates/themes/general.json templates/themes/my_vertical.json

# 2. Edit name, label, description, set "extends": "general"
# 3. Add 5–10 vertical-specific negative themes
# 4. Add 3–5 vertical-specific positive themes
# 5. Smoke test against a known app in that vertical
python -m scripts.run_pipeline --play com.example --themes my_vertical \
    --formats json --output /tmp/test

# 6. Inspect the JSON output for theme tag distribution
cat /tmp/test/full_analysis.json | python -m json.tool | grep -A 2 neg_counts
```

## How many themes is right?

Sweet spot is **6–12 negative themes** and **4–8 positive themes** per vertical (including inherited).

Too few: reviews get tagged with the same 2 themes, the analysis is shallow.
Too many: every theme has 1-2 mentions, no clear signal.

The HTML report shows the top 6 negative and top 5 positive themes — anything beyond that gets ignored. So aim for those numbers being meaningful and useful.

## What if my app doesn't fit any vertical?

Use `general`. It's broad enough to catch the common stuff. The downside: vertical-specific complaints (e.g., "the tests are inaccurate" for a fertility app) won't be tagged. The reviews are still in the report — they just won't roll up into a named theme.

The right long-term answer is to write a custom taxonomy for your vertical and submit it back to the project (see CONTRIBUTING.md).

## Should I edit a shipped taxonomy?

Local edits are fine. **Don't** submit PRs that drastically change a shipped taxonomy without discussion — other users depend on stable keyword lists.

PRs that **add** keywords to existing themes (e.g., catching a phrase the original missed) are welcome.

PRs that **remove** keywords need justification — usually showing real false positives.

PRs that **rename** themes are mostly rejected — they break backward compatibility for anyone using the JSON output programmatically.
