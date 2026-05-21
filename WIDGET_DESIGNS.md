# Widget Designs — AI Computer Sidekick

Two complete widget designs exist in this repo. The **live** design (loaded by default) is the
Liquid-Glass v2 corner orb. The **Spotlight Pill** is preserved as a reference/alternative in
`static/widget-spotlight/`.

---

## 1. Liquid-Glass Sidekick v2 (LIVE)

**Location:** `static/index.html`, `static/app.js`, `static/style.css`

**Visual:**
- Corner pill-shaped toggle button (178×64 px) bottom-right, liquid-glass frosted background with
  shimmer shine, a square icon core, a two-line copy block (kicker + live state text), and a
  3-bar animated audio meter.
- Toggle expands into a full panel (376 px wide) with an aurora shimmer overlay, brand sigil
  header, live activity row with pulsing dot, a scrollable step-feed (vpanel-steps), chat log, and
  a compose row (mic + text input).

**Behavior:**
- Drag-to-reposition: the toggle button and panel header are draggable; final position is clamped
  to the viewport and persisted in `localStorage` under `ai-computer.vorb-position.v2`.
- `Ctrl+Shift+Space` global shortcut toggles the orb open/closed.
- `syncSteps()` polls the DOM every 700 ms and renders the last 5 agent-step titles as vstep rows.
- Widget-shell mode (`?widget=1` query param): adds `widget-shell` CSS class, hides the rest of
  the dashboard, and shows the panel full-screen inside a frameless pywebview window.

**Desktop launcher:** run `python run_desktop.py --widget` to open a frameless 410×560
always-on-top window showing only the sidekick panel.

---

## 2. Spotlight Command Pill (REFERENCE)

**Location:** `static/widget-spotlight/index.html`, `static/widget-spotlight/app.js`,
`static/widget-spotlight/style.css`

**Visual:**
- 484×56 px frosted-glass horizontal pill, 28 px radius, anchored **top-center** of the screen.
- Small monitor logo on the left (cyan-tinted).
- `"Start a task..."` text input as the focal element.
- 4-bar animated equalizer shown only while busy/listening.
- Round mic + round cyan send + minimize buttons inline.
- Cyan accent palette (`#5be0d0` dark / `#14a99a` light); pill grows a soft cyan glow ring during
  a running task.
- Reply bubble drops below the pill (not a chat log — just the latest answer with a dismiss ×).
- Theme-aware glass via `--vp-*` CSS vars (light = white frost, dark = near-black frost).

**Behavior:**
- Dashboard mode: a small dock orb (52 px) lives bottom-right; click it to summon the pill at
  top-center; minimize returns to the orb.
- Widget mode (`?widget=1`): pill is permanently shown at the top; reply bubble below; the pill
  itself is the OS drag region (buttons + input excluded).
- `speakAgentReply` unwraps `{"reason":"..."}` JSON and renders the answer into the reply bubble.
- Activity text replaces the input placeholder during busy/listening — the pill acts as a live
  status line.

**How to activate:** swap the three files from `static/widget-spotlight/` back into `static/` and
adjust `run_desktop.py` window size to 520×320.

---

## Switching between designs

| Step | Command |
|------|---------|
| Use Spotlight pill | `cp static/widget-spotlight/{index,app,style}.* static/` |
| Use Liquid-Glass v2 | Already live — no changes needed |
| Side-by-side compare | Open `static/widget-spotlight/index.html` directly in a browser |
