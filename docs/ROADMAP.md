# Roadmap: Best Open-Source AI Windows App

Orynn wins by being local, visible, free-model friendly, and Windows-native.

## Now

- UIA-first desktop control: click controls by name, not pixels.
- Floating capsule + dashboard.
- Coding, browser, and desktop modes.
- Free-first OpenRouter routing with optional stronger model overrides.
- Permission scopes, approval gates, and untrusted-content boundaries.
- Windows release zip built from tags.

## Next: Make It Feel Magical

1. **Demo-first onboarding**
   - One-click sample task.
   - Built-in "try Notepad demo" button.
   - README GIF/video.

2. **Task-scoped browser sessions**
   - Each task gets its own browser context.
   - No cross-task page clobbering.
   - Clean browser teardown on task completion.

3. **Free-model turbo mode**
   - Prefer UIA text/context over screenshots.
   - Short prompts for atomic tasks.
   - Stronger model only for stuck/retry moments.
   - Step and token budgets visible in UI.

4. **Trust dashboard**
   - Show active permissions by task.
   - Explain why each permission is needed.
   - Revoke all permissions with one click.
   - Local-only session state by default.

5. **Benchmarks**
   - Publish repeatable runs for UIA vs screenshot workflows.
   - Track task duration, steps, screenshot count, and pass rate.

6. **Installer**
   - Move from release zip to signed installer.
   - Start Menu shortcut.
   - First-run `.env`/key wizard.

## Later

- macOS accessibility support.
- Linux AT-SPI support.
- Optional local-only model bundle.
- Plugin marketplace for safe, reviewed workflows.
- Recorded task replays for debugging and sharing.

## Non-Goals

- Hosted remote-control service by default.
- Blindly auto-approving destructive actions.
- Fake benchmark claims without raw results.
