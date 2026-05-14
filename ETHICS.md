# Ethics

Short version: **only use public data, don't harm anyone, attribute properly.**

This skill collects review data from public review feeds operated by Apple and Google. That data was published by real people — usually during a frustrating or moving moment in their lives. Treat it accordingly.

## What this skill is for

- Understanding how users actually feel about an app
- Surfacing patterns across hundreds of reviews that no human would catch reading one-by-one
- Producing client deliverables, internal product research, and competitive intelligence
- Helping product teams prioritize what to fix

## What this skill is NOT for

These uses are out-of-scope, and the maintainers will close issues / reject PRs that enable them:

1. **Harassment of app developers.** Don't compile lists of negative reviews to brigade an app or its team. Don't dox developers from reviews. Don't use the output to launch coordinated campaigns.

2. **Manipulating review systems.** Don't use the scraped data to train an LLM that generates fake reviews. Don't use cross-store comparison to plan negative SEO. Don't use the 4-star "almost loyal" analysis to identify reviewers for retaliation.

3. **Republishing without analysis.** This skill produces analytical reports. Don't strip out the analysis layer and republish raw review text as your own content. That is plagiarism, not research.

4. **Aggressive scraping.** The defaults in this skill are deliberately conservative — small sleep delays, capped page counts, polite user agents. Don't override those defaults to hammer Apple or Google's servers.

5. **Misrepresenting attribution.** Reviews quoted in reports include the reviewer's display name and country, both of which they chose to make public when they posted. **Do not** use this skill to identify reviewers by full name, link their reviews to their other identities, or otherwise attempt deanonymization. Display names in stores are sometimes real names — treat them as the reviewer chose to be addressed, nothing more.

## Rate limits and respect

This skill ships with built-in pacing:

- 0.2 second sleep between Play Store queries
- 0.3 second sleep between App Store RSS pages
- Maximum 10 pages per country on App Store (Apple's own limit)
- Polite `User-Agent` header that identifies the tool

If you find yourself wanting to disable these, **stop and reconsider**. There are better tools for high-volume scraping (commercial APIs that pay the stores for access). This skill is for one-shot analyses.

If a store returns a 503 or 429, the skill stops trying. Don't add retry loops. The store is telling you to come back later.

## Privacy

Reviews are public. The reviewer's display name is public. But aggregating public data has its own ethics:

- **No reverse search.** Don't write tools on top of this skill that search for a reviewer's posts across other platforms.
- **Don't store personally identifying details.** Country codes are fine. Full names matched to email addresses are not.
- **Aggregate by default.** When sharing results externally, lead with aggregate stats (themes, percentages) and use individual quotes sparingly to illustrate the pattern.

## Fair use of quoted reviews

Reviews are short and the skill quotes them in full where space allows. Two principles:

1. **Attribution always.** Every quote shown in the HTML reports includes the reviewer's display name and store. Don't strip that out before publishing.
2. **Critical commentary, not republication.** The quotes appear *inside* a thematic analysis, not as a list of "best 1-star reviews about X." That difference is what makes this fair use under most jurisdictions.

If you're publishing the reports externally (blog post, public client deliverable, conference talk), it's polite to also link to the original app store listing so readers can see the full context.

## Disclosure when used in commercial work

If you use this skill to produce a deliverable for a paying client, that's fine. You don't need to credit the skill explicitly, but if a client asks how you produced the analysis, be honest. The reports are clearly machine-aided.

If you use this skill to produce content that's then sold *as* the analysis ("buy our $99 review analysis report"), be transparent that it's automated. Don't pretend a human spent days reading reviews.

## When to NOT use this skill

There are categories of apps where review scraping has more weight than usual. Use extra discretion:

- **Mental health and crisis apps.** Reviews often describe acute distress. The skill is technically capable of scraping them, but consider whether your analysis really needs that data.
- **Apps targeting children.** Children's apps sometimes have parents reviewing on their kid's behalf, with details about the child. Skip those data points.
- **Niche identity apps.** Apps for specific communities (LGBTQ+ dating, addiction recovery, immigration support) have reviews that may identify users implicitly. Aggregate ruthlessly; quote rarely.

## If you spot misuse

Open an issue. The maintainer (and the community of forks) will work to:

- Add safeguards if the misuse pattern is preventable in code
- Document the misuse as out-of-scope
- Pull the offender's right to use the project where possible (the MIT license has limits but reputation matters)

## A note on the model behind this

This skill was built with Claude. Anthropic has its own usage policies governing what Claude will and won't help with. If you ask Claude to use this skill to do something the Anthropic Usage Policy prohibits — coordinated harassment, generating fake reviews, surveillance — Claude will decline regardless of what this skill technically can do.

That is not a bug. That is the system working.

---

If you read this far: thank you. Most ethics docs go unread. The fact that you read this one suggests you're going to use this skill well. Build good things.
