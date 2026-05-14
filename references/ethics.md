# Ethics (skill-internal reference)

See the project-root [ETHICS.md](../ETHICS.md) for the full rules. Short version for Claude to surface when relevant:

## Always tell the user

When the skill runs, the data being collected is the published reviews of real people. Treat that responsibly:

- Lead with aggregate stats (themes, percentages)
- Use individual quotes sparingly and only with attribution
- Don't help users identify reviewers across platforms
- Don't help users compile lists of "reviewers to retaliate against" from negative reviews
- Don't generate fake reviews using scraped patterns

## When to surface ethics to the user

Most use cases are fine — researchers, product teams, founders, agencies. Mention ethics actively when:

- The user asks about *individual* reviewers ("Who said X?") — gently redirect to the pattern
- The user wants to compile a list of negative reviewers — decline and explain
- The user asks to "find users who would respond to a campaign" — out of scope
- The user is analyzing a mental health, crisis, or children's app — suggest extra discretion

## What the skill itself prevents

- Built-in rate limits (don't override)
- 10-page cap per country on App Store RSS (Apple's own limit, respected)
- User-Agent header that identifies the tool
- Stops on first 503/429 (doesn't pound the API)

## What the skill outputs intentionally include

- Reviewer display names (they chose to be public)
- Country codes (they posted from that storefront)
- App version (they were running that version)

## What the skill never outputs

- Reviewer email addresses (we never have them)
- Reviewer location beyond country (we don't have it)
- Links to reviewers' other content (we don't look)
- Any "cross-reviewer" inference

If a user wants information beyond what the skill produces by default, that's the user's responsibility — the skill won't help them.
