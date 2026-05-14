# Input Formats

How to specify which app to analyze. The skill accepts three forms.

## 1. Play Store package name

The `id=` parameter from any Play Store URL:

```
com.proov
com.duolingo
com.notion.id
com.calm.android
```

Pass it as `--play <package_name>`.

## 2. App Store numeric ID

The number after `/id` in any App Store URL:

```
1574349479    (Proov)
571800810     (Calm)
570060128     (Duolingo)
```

Pass it as `--appstore <id>`.

## 3. Full URLs

The skill extracts IDs from URLs automatically — no need to parse yourself:

```bash
--play "https://play.google.com/store/apps/details?id=com.proov"
--appstore "https://apps.apple.com/us/app/proov/id1574349479"
```

Trailing query strings (`?country=us&hl=en`) are stripped.

## 4. App name only (Claude only)

When invoked from Claude with just a name ("analyze reviews for Calm"), Claude:

1. Searches the web for the Play Store and App Store URLs
2. Extracts the IDs
3. Confirms with the user before scraping ("I found these — proceed?")

This step happens in Claude's conversation, not in the Python pipeline. The pipeline always needs explicit IDs or URLs.

## Both stores or just one?

The most useful analysis uses both stores because cross-store comparison is the most interesting analytical move. But the skill works fine with either alone:

```bash
# Both stores (recommended)
--play com.proov --appstore 1574349479

# Play Store only
--play com.proov

# App Store only
--appstore 1574349479
```

When only one store is available, the executive summary is replaced with a simpler single-store version and the cross-store comparison section is skipped.

## Countries

Default: `us,gb,ca,au` — the four largest English-language storefronts.

```bash
--countries us,gb,ca,au,nz,ie
```

App Store RSS returns ~50 reviews per page × 10 pages per country = ~500 max per country. Adding more countries gets you more total reviews but with diminishing returns (smaller storefronts often return 0).

Play Store dedupes automatically across countries — adding more locales improves coverage of multilingual apps but rarely adds many English reviews.

## What if the app isn't on one of the stores?

Just pass the store it IS on. The skill produces a single-store report.

If neither store has it, the skill can't analyze it — there's no public review feed to scrape.

## What about Mac App Store, iPad-specific, or Apple TV apps?

The Apple iTunes RSS feed only covers the iOS App Store reliably. Mac App Store reviews are technically there but very sparse. iPad and Apple TV reviews are included in the iOS feed when the app is universal.

## What about Amazon Appstore, Galaxy Store, or alternative Android stores?

Not supported. Google Play covers >95% of Android usage outside of mainland China. Alt-store coverage would require entirely different scrapers.
