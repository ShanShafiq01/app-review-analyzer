---
description: Analyze App Store and Play Store reviews for any mobile app. Pass a URL, package name, or app name.
---

# /review-analyze — App Review Analyzer

Run a full competitive review analysis on a mobile app. Output goes to `./output/<app_slug>/`.

## Usage

```
/review-analyze https://apps.apple.com/us/app/your-app/id1234567890
/review-analyze com.example.app
/review-analyze "Your App Name"
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

4. **Run the pipeline.** If installed as a Claude Code plugin (`${CLAUDE_PLUGIN_ROOT}` is set), use the plugin's bundled Python. The bash block auto-bootstraps the venv on first run — no manual setup step needed.

   ```bash
   # Resolve the plugin directory (falls back to cwd for git-clone installs)
   PLUGIN_DIR="${CLAUDE_PLUGIN_ROOT:-$(pwd)}"

   # Find the venv Python (Mac/Linux uses .venv/bin/, Windows uses .venv/Scripts/)
   PY="$PLUGIN_DIR/.venv/bin/python"
   [ -x "$PY" ] || PY="$PLUGIN_DIR/.venv/Scripts/python.exe"

   # First-run bootstrap: install Python deps if the venv doesn't exist yet
   if [ ! -x "$PY" ]; then
     echo "First-time setup — installing Python dependencies (~30-60 seconds)..."
     if [ -f "$PLUGIN_DIR/setup.sh" ]; then
       bash "$PLUGIN_DIR/setup.sh"
     elif [ -f "$PLUGIN_DIR/setup.ps1" ]; then
       powershell -ExecutionPolicy Bypass -File "$PLUGIN_DIR/setup.ps1"
     fi
     # Re-resolve PY after setup
     PY="$PLUGIN_DIR/.venv/bin/python"
     [ -x "$PY" ] || PY="$PLUGIN_DIR/.venv/Scripts/python.exe"
   fi

   # Run the pipeline. PYTHONPATH lets `-m scripts.run_pipeline` find the package
   # without changing cwd, so --output is relative to the user's current directory.
   PYTHONPATH="$PLUGIN_DIR" "$PY" -m scripts.run_pipeline \
     --play <package_name> \
     --appstore <numeric_id> \
     --themes auto \
     --formats html,excel,csv \
     --output ./output/<app_slug>
   ```

   The bootstrap is **idempotent and automatic** — the second `/review-analyze` call (and every call after) skips setup instantly because the venv already exists.

5. **Present the files** so the user can actually open them. Channel-dependent:
   - **claude.ai (sandboxed):** write outputs to `/mnt/user-data/outputs/<app_slug>/` and call `present_files` — gives the user one-click download buttons in chat.
   - **Claude Code (local filesystem):** output each generated file as a clickable markdown link using an absolute `file://` URL (e.g., `[executive_summary.html](file:///absolute/path/here.html)`) and include an `open <path>` command for the non-clickable case. Use absolute paths, not `~/...` (markdown links don't expand tildes).
   Always lead with `executive_summary.html` — it's the highest-value deliverable.

6. **Briefly summarize** the top 2-3 findings in chat so the user knows what to look at first.

## Examples

```
You: /review-analyze https://apps.apple.com/us/app/your-app/id1234567890

Claude: I'll analyze <Your App>. Both stores, default formats? [Y/n]

You: y

Claude: [runs pipeline, ~90 seconds]

Done! 196 App Store + 234 Play Store reviews analyzed.

Top three findings:
  1. Subscription friction is the #1 complaint on both stores (28% of negative reviews)
  2. Top positive theme: <feature name> (42% of 5-star praise)
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
