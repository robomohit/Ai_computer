# Floating widget — Liquid-Glass Command Capsule

The AI Computer floating widget is a single **liquid-glass command capsule** —
one ambient pill, no chrome. Modeled on Perplexity Personal Computer's command
surface.

## Anatomy

`#vorb-root` → `.vcap` (the capsule). Markup in `static/index.html`, styling in
`static/style.css` (search `liquid-glass command capsule`), behaviour in
`static/app.js` (`capsuleWidget()` IIFE).

**Primary row** (`.vcap-row`, ~66px tall):
- `.vcap-logo` — monitor sigil, accent-tinted, doubles as the drag grip.
- `.vcap-field` — the task input (`#vpanel-text`) with an overlaid live-status
  line (`#vpanel-activity-text`) that replaces the placeholder while busy.
- `.vcap-wave` — a `<canvas>` dot-matrix waveform; animates only while the
  agent is busy or listening (rAF stops at idle to save CPU).
- `.vcap-mic` / `.vcap-send` — round action buttons.
- `.vcap-close` — only shown in widget-shell mode.

**Reply** (`.vcap-reply`): hidden until the agent answers, then it grows the
capsule downward — the answer lives *inside* the capsule, not a separate panel.

## Behaviour

- **Funnels into the existing pipeline** — typing/voice writes to the main
  composer (`#input`) and clicks `#send`; zero new task plumbing.
- **Voice** — tap the mic, speak, it auto-submits on the final transcript.
- **State mirror** — a 700 ms poll reads `currentStatus` / `liveStatusMessage`
  and drives the status line, glow ring, and waveform.
- **Drag** — dashboard mode: grab the logo to reposition; saved under
  `localStorage["ai-computer.vorb-position.v2"]`. Widget-shell mode: pywebview
  `easy_drag` moves the OS window.
- **Shortcut** — `Ctrl+Shift+Space` focuses the capsule input.
- **Theme** — theme-aware glass via `--cap-*` vars; widget-shell mode forces
  dark glass (reads best floating over an arbitrary desktop).

## Widget-shell mode (`?widget=1`)

When the page is loaded with `?widget=1` (or `?sidekick=1`) it adds the
`widget-shell` class, hides every dashboard surface, makes the body
transparent, and anchors the capsule to the top of the window — so the native
pywebview window *is* the floating capsule.

## Desktop launcher

`python run_desktop.py --widget` opens a frameless, transparent, always-on-top
600×320 pywebview window pointing at `/?widget=1`. Without `--widget` it opens
the full dashboard.

## History

Earlier iterations (corner orb, expandable panel, Spotlight pill) are
superseded — the capsule is the single canonical design. Do not re-introduce a
separate `static/widget-spotlight/` copy; there is one widget.

## Capsule V2: Adaptive Command Surface

The capsule is now treated as a tiny stateful control surface, not just a glass input. Both the web capsule and native Qt capsule expose:

- **Scope** - the active computer surface, selected app/window, folder, image, clipboard, or attachment.
- **Perception** - whether the agent is ready, using attached context, taking voice input, seeing the screen, or paused for approval.
- **Phase** - idle, focused, context-ready, submitting, planning, acting, waiting for approval, paused, done, or error.
- **Controls** - Pause, Stop, and Details live on the capsule while work is active.
- **Context actions** - the web capsule suggests quick actions based on mode and scope: browser page actions, workspace/test actions, folder cleanup, or desktop screen actions.
