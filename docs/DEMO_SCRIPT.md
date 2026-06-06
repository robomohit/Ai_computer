# Orynn Demo Script

Use this to record the README GIF/video. Keep it short: 30-45 seconds is ideal.

## Goal

Show the one thing that makes Orynn different:

> It drives Windows apps by UI Automation control names instead of screenshot/pixel guessing.

## Recording Setup

- Resolution: 1280x720 or 1600x900.
- Theme: dark.
- Start from the floating capsule (`start.bat`), not the browser dashboard.
- Close unrelated windows and notifications.
- Use a free OpenRouter model so the demo proves the free-first path.

## Demo 1: Notepad UIA Control

Prompt:

```text
Open Notepad, type a short release note for Orynn, save it to Desktop as orynn-demo.txt, then tell me where it is.
```

What to capture:

1. `Ctrl+Shift+Space` summons the capsule.
2. Orynn launches Notepad.
3. The live ticker shows UIA/tool actions.
4. It types and saves the file.
5. Final message confirms the path.

## Demo 2: Browser + Desktop

Prompt:

```text
Search the web for the latest Orynn release page, summarize what changed, and copy the summary to Notepad.
```

What to capture:

1. Browser mode opens GitHub.
2. It reads the release page.
3. It switches to Notepad via desktop control.
4. It writes the summary.

## README Asset

Save the final GIF as:

```text
docs/demo.gif
```

Then replace the hero image in `README.md` with:

```html
<p align="center">
  <img src="docs/demo.gif" alt="Orynn controlling Windows apps by UI Automation" width="820">
</p>
```

## Social Clip Caption

> Orynn is a local Windows AI agent that clicks controls by name instead of guessing pixels. It runs on free models, shows every step, and ships as a desktop app.
