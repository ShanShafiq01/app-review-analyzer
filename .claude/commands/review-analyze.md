---
description: Analyze App Store and Play Store reviews for any mobile app. Pass a URL, package name, or app name.
---

# /review-analyze — App Review Analyzer

Run a full competitive review analysis on a mobile app. Output goes to `./output/<app_slug>/`.

## Usage

```
/review-analyze https://apps.apple.com/us/app/calm/id571800810
/review-analyze com.duolingo
/review-analyze Notion
```

## Workflow

When invoked, follow the App Review Analyzer skill workflow:

1. **Parse the argument:**
   - If it's a Play Store URL → extract package name as `play_id`
   - If it's an App Store URL → extract numeric ID as `appstore_id`
   - If it's a package name (`com.x.y`) → use as `play_id`, search for App Store version
   - If it's a numeric ID → use as `appstore_id`, search for Play Store version
   - If it's a name → web search for both store URLs

2. **Confirm the app** if there's any ambiguity — show what you found and ask "Proceed?"

3. **Ask one question** about formats unless the user already specified:
   - HTML only
   - HTML + Excel + CSV *(default — recommended)*
   - Everything (HTML + PDF + Excel + CSV + Markdown + JSON)

4. **Run the pipeline:**
   ```bash
   python -m scripts.run_pipeline \
     --play <package_name> \
     --appstore <numeric_id> \
     --themes auto \
     --formats html,excel,csv \
     --output ./output/<app_slug>
   ```

5. **Present the files** using `present_files`, leading with the executive summary HTML.

6. **Briefly summarize** the top 2-3 findings in chat so the user knows what to look at first.

## Examples

```
You: /review-analyze https://apps.apple.com/us/app/calm/id571800810

Claude: I'll analyze Calm — Meditation & Sleep. Both stores, default formats? [Y/n]

You: y

Claude: [runs pipeline, ~90 seconds]

Done! 196 App Store + 234 Play Store reviews analyzed.

Top three findings:
  1. Subscription friction is the #1 complaint on both stores (28% of negative reviews)
  2. Sleep stories drive 42% of 5-star praise
  3. iOS users rate 0.32★ higher than Android

[presents 3 HTML files + Excel + CSVs]
```

## Don't

- Don't show raw HTTP errors or stack traces to the user
- Don't dump every progress message — summarize at the end
- Don't ask more than one question
- Don't proceed without confirming the app identity if you searched for it

## Reference

Full skill documentation in `SKILL.md`. Output format details in `references/output_formats.md`.
