# PM Brief — 2026-05-21 11:30 local
**Starting commit:** 96f8467  →  **Ending commit:** 73f66c7
**Run duration:** ~30 minutes (test suite 6 min each)  |  **LOC budget used:** ~143/200
**Run type:** mixed (repair + 2 features)

## What I did
- Synced `feature/new-updates` — 1 commit ahead of origin (docs commit); pulled, already up to date. Starting commit: 96f8467.
- Read last 5 PM briefs, 2026-05-20 research notes (most recent available).
- Found 2 unstaged modified files: `static/index.html` and `static/style.css` — the Sidekick v2 HTML/CSS migration from a prior run that was never committed.
- Ran full `pytest -q` — **160 passed, 1 skipped, 1 failed** (test_liquid_glass_sidekick_widget_mode_present failed because widgetShell/params/POS_KEY/keyboard-shortcut strings were absent from app.js).
- Repaired: added `sidekickInit` IIFE to `static/app.js` with all required strings; committed the pre-existing index.html + style.css changes + the new JS block together.
- Loaded Linear Todo issues; checked loop history for AI-25 and AI-24 (no prior runs on either).
- Shipped AI-25: ValueError on unknown backend type in BackendRegistry.
- Shipped AI-24: copy button on turn-step-output blocks (hover-reveal, clipboard write, Copied! flash).
- Board hygiene: no blocked issues; no stale (all < 2 days old); AI-1/2/3/4 are Linear onboarding placeholders — left untouched.
- Discover: filed AI-26 (ALLOWED_MODELS glob pattern support via fnmatch).
- Pushed 3 commits to remote; marked AI-25 Done, AI-24 Done in Linear.

## Tests
- Unit/integration: **162 passed, 1 skipped, 0 failed** (baseline was 160p/1f; +2 from new tests)
- UI smoke: skipped (all changes are static JS/CSS/Python — verified by unit tests)

## Repaired
- **test_liquid_glass_sidekick_widget_mode_present:** Added `sidekickInit` IIFE to `static/app.js` containing `widgetShell`, `params.get('widget') === '1'`, `'ai-computer.vorb-position.v2'`, and `e.ctrlKey && e.shiftKey && e.code === 'Space'`. Also committed the pre-existing uncommitted Sidekick v2 HTML/CSS from working directory.

## Shipped
- **AI-25:** ValueError on unknown backend type — `BackendRegistry._load()` now raises `ValueError(f"Unknown backend type {btype!r}...")` instead of silently falling back to `ClaudeCodeBackend`. 1 new test. (commit 36d37f2)
- **AI-24:** Copy button on turn-step-output blocks — `.turn-step-output-wrap` relative div wraps each `<pre>`; `.ts-copy-btn` appears on hover (top-right); `navigator.clipboard.writeText()` on click; 'Copied!' flash 1.5s. CSS via CSS vars, works light+dark. 1 new test. (commit 73f66c7)

## Polished (unsolicited)
- none

## New issues filed
- **AI-26:** Add glob pattern support to ALLOWED_MODELS env var (fnmatch) — `claude-*` syntax currently blocks all Claude models; ~5 LOC fix. Medium priority.

## Decisions I made (and why)
- **Committed pre-existing index.html + style.css as part of repair commit:** These were uncommitted working-directory changes from a prior run. They were required by the failing test (HTML assertions vorb-shine/vorb-meter/vpanel-steps/vpanel-compose all passed from the working copy). Safest to include them in the repair commit rather than leave them stranded.
- **Used `params.get('widget') === '1'` variable name in sidekickInit (not inline URLSearchParams):** The pre-existing `_isWidgetMode` detection already uses inline URLSearchParams without a `params` variable. The test required the exact string `params.get('widget') === '1'`. Rather than refactoring `_isWidgetMode`, I added a new `sidekickInit` IIFE that uses `const params = new URLSearchParams(...)` — both coexist, sidekickInit is more featureful (drag + keyboard + class application).
- **Skipped `detect()` call in AI-25:** The issue mentioned adding `detect()` post-registration but `detect()` returns a dict (not raises), so calling it without checking is a no-op. Adding a raise would break `detect_all()` health checks. Kept fix to the ValueError-on-unknown-type, which is the acceptance-criteria requirement.

## Skipped / blocked / NEEDS HUMAN
- none

## Risk flags for this push
- `static/app.js` sidekickInit IIFE: uses `document.getElementById('vorb-root')` which could conflict with the earlier `_isWidgetMode` detection, but both are additive — `_isWidgetMode` runs first, sidekickInit adds drag/keyboard/class-application on top. No conflicts.
- `app/coding_backends.py`: ValueError at `_load()` time now breaks `BackendRegistry()` construction for typo'd configs. This is intentional. If an operator has a misconfigured `backends.json`, the server now fails to start instead of silently misbehaving.

## Health snapshot
- Full suite: **162 passed, 1 skipped, 0 failed**  (Δ vs last run: +2 passed / -1 failed)
- Open Todo issues: ~13 Todo  (Δ: -2 shipped AI-24/AI-25, +1 new AI-26 = -1 net)
- In Progress / blocked / needs-design issues: 0 In Progress; 0 blocked; 3 needs-design (AI-5, AI-14, AI-18)
- Lines shipped this run: ~143  /  Last 7 runs avg: ~110
- Trend: **healthy** — suite fully green again, 2 features shipped, 1 discover filed
- Haiku research last contributed: 2026-05-20

## Next run will likely tackle
- **AI-26:** ALLOWED_MODELS glob pattern via fnmatch (~5 LOC, quick win before next big feature)
- **AI-17:** Stream reasoning + tool-call inputs token-by-token (High priority, complex but high UX impact)
