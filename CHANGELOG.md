# Changelog

## Unreleased

### Swarm racing — parallel free providers, fastest token wins
- When a Groq key AND an OpenRouter key are both set, every native tool-call
  step now runs on BOTH providers simultaneously; whichever streams a token
  first wins and the loser is cancelled. Free tokens cost $0 and rate limits
  are per-provider, so this turns parallelism into free capacity: step latency
  becomes min(providers) instead of one provider's TTFT, and a Groq 429 is
  invisible — the OpenRouter candidate is already in flight and simply wins
  the race (no model swap, no backoff ladder). UI shows "⚡ {provider}
  answered first". Kill switch: ORYNN_SWARM_RACE=0.

### Workflow compiler — successful runs replay with zero model calls
- The first clean multi-action run of a goal now COMPILES: the verified action
  sequence is stored (~/.ai_computer/traces.json, ORYNN_TRACE_STORE to move).
  The next run of the same goal seeds the batched-action queue with the trace
  and replays it action-by-action — every step still passes the full safety/
  approval/permission/verification machinery, but the model is consulted
  exactly ONCE, at the end, to verify the observations and finish. A replayed
  action that fails retires the trace ("Replay diverged") and hands control
  back to live planning mid-task, which recovers and recompiles on its next
  success.
- **Near-miss retrieval** — a similar-but-not-identical goal doesn't replay;
  its trace is injected into the system prompt as a few-shot
  `<past_success_hint>` (the winning action sequence, with a warning to adapt
  args) — retrieval-augmented acting for free models that can't be fine-tuned.
- Test isolation: the suite pins ORYNN_TRACE_STORE to a per-test tmp file so
  traces never leak between runs or into the user's real store.

### Free-model token diet (speed: smaller, cache-stable prompts)
- **Goal-relevant tool schemas** — the unified surface shipped 83 tool schemas
  (~6.6K tokens) with EVERY model call. Schemas are now selected by goal
  relevance (weather question: 14 tools/~1.2K; coding goal: ~26/2K) with a
  `request_more_tools` escape hatch that unlocks the full catalog in one cheap
  turn if the trim guessed wrong. XML guidance stays full (it's baked into
  system prompts once and must not go stale). Desktop grant mid-task force-
  includes the desktop packs.
- **Compact schema descriptions** — native tool schemas embedded the full
  teaching prose per tool; they now carry just the first sentence (the prompt
  decision table keeps the long-form teaching).
- **Cache-stable history** — old messages were truncated in place EVERY step,
  changing the prompt prefix each call and defeating Groq/OpenRouter prefix
  caching. Compression now only triggers past a ~28K-char budget, so short and
  medium tasks keep byte-identical prefixes (faster TTFT, cheaper).
- **XML repair ladder** — a stream that dies before `</action>` now salvages
  the args body, and args that fail both JSON parses bounce back to the model
  with the raw text instead of executing the action with silently-empty args.

### Liquid glass + capsule fine-tuning (verified in live preview)
- **Light-mode sidebar reads as glass again** — the rail blurred cream-over-
  cream (white 0.72/0.42 gradient over a near-white tint) and was invisible
  against the feed. Less white over a slightly deeper gray-blue rail tint plus
  a firmer hairline gives real separation; verified via preview screenshots in
  both themes, zero console errors through onboarding → theme flips → a full
  demo task stream.
- **Capsule skips backdrop sampling while hidden** — the adaptive-glass timer
  grabbed the screen every 1.5s even when the capsule wasn't visible.
- **Offscreen Qt test suite for the capsule** — pins the light-palette flip
  (no more white-on-white card text) and the delete-button two-tap confirm.

### Free-model harness (speed + accuracy)
- **Constrained JSON decoding** — `plan_hierarchical`, `reflect_on_subtask`,
  and `evaluate` now request `response_format: json_object` (Groq/OpenAI/
  OpenRouter), `response_mime_type: application/json` (Gemini), or
  `format: json` (Ollama), so a malformed plan/reflection becomes structurally
  impossible on models that support it. Models that reject the param get one
  automatic retry without it — never a hard failure.
- **Parallel tool calls now actually execute.** The native tool stream emitted
  every parallel call, but the agent loop overwrote the action each time —
  only the LAST call ran and the rest silently vanished. Parallel calls are
  now queued and executed strictly in order on subsequent loop steps with NO
  extra model round-trip (the free-tier latency win). A failed action clears
  the queue so the model re-plans from the failure observation — checkpoint
  semantics. System prompts now tell the model to batch independent calls;
  Groq/OpenAI requests set `parallel_tool_calls: true`.
- **Malformed tool args bounce instead of executing as `{}`.** Unparseable
  tool-call arguments used to silently become empty args (a `write_file` with
  no content, a click with no coords). The stream now flags `args_error`, and
  the agent feeds the raw broken payload back to the model with instructions
  to resend — the action never runs on garbage.
- **History coercion is free-model-safe** — multi-turn seeding now trims long
  turns at a line boundary, closes dangling code fences, and appends an
  explicit `…[earlier content trimmed]` marker instead of slicing mid-word.
- **Max-steps failure copy humanized** — "Max steps reached (25) without
  finish action." is now a plain-language message telling the user progress
  is saved and 'continue' resumes.

### Capsule (Qt)
- **Light-mode cards are readable again** — item rows, dividers, buttons, and
  the dismiss chip hardcoded dark-surface colors (near-white text), which made
  list widgets invisible on the light card surface the adaptive palette picks
  over bright desktops. All card chrome now flips with `set_card_palette`.
- **Destructive widget buttons need a second tap** — the icon-only trash
  button POSTed `/api/capsule/delete` for every listed file on a single
  (possibly stray) click. Delete-style actions now arm with "Click again to
  confirm" and auto-disarm after 4s. HTTP action feedback also survives
  non-JSON/non-dict responses instead of mislabeling success as an error.

### Dashboard
- **Streaming replies no longer re-render the world** — the reply stream
  appended each tick by re-running the full markdown+sanitize pipeline over
  the entire accumulated text every 26ms (O(n²), janks long answers). Ticks
  now append plain text; markdown renders exactly once at finalize, matching
  the live delta path.

### Fast/accurate on free models — polish pass
- **Capsule cards readable in light mode** — list-item names, details, icons,
  dividers, and secondary/danger buttons hardcoded dark-mode colors, so when
  the adaptive glass flipped light the card surface went near-white and the
  near-white text became invisible. All card chrome now flips with
  `set_card_palette`.
- **Two-tap confirm on destructive widget buttons** — the icon-only trash
  button deleted every listed file on a single (mis)click; delete endpoints now
  arm on first tap ("Click again to confirm", auto-disarms in 4s).
- **Widget HTTP feedback hardened** — a non-JSON or non-dict success response
  no longer reports a false "Error" for an action that actually succeeded.
- **Dashboard streaming is O(n)** — the synthetic reply stream re-ran the full
  markdown+sanitize pipeline over the whole accumulated text every 26ms
  (O(n²), visible jank on long answers). Ticks now append plain text; markdown
  renders exactly once at finalize. Demo stream now ends with a real assistant
  reply (verified live: plain text while streaming, bold/code/lists after).
- **History trimming no longer corrupts context** — follow-up turns over 2000
  chars were cut mid-word, leaving dangling code fences that derail free
  models. Trims now land on a line boundary, close any open fence, and append
  an explicit "…[earlier content trimmed]" marker. (+2 tests)
- **Human max-steps message** — "Max steps reached (25) without finish
  action." → tells the user progress is saved and to send "continue".
- **`.claude/launch.json` cwd fix** — the preview server config pointed at the
  stale nested `Ai_computer/` copy, silently serving old code.

### Desktop input (drag/hold — games + timeline editors like CapCut)
- **Real from→to drags** — `left_click_drag` now accepts `start_x`/`start_y`
  (press at the source, glide, release at the target) instead of dragging from
  wherever the cursor happened to be. The drag presses, HOLDS ~150ms so the app
  registers drag mode, glides with distance-scaled duration, settles ~120ms,
  then releases — the press/settle pauses are what timeline editors (CapCut,
  Premiere) and games need; `pyautogui.dragTo` skipped both, so drags silently
  failed. Coordinates are clamped, the button is force-released on error, and
  the politeness gate + synthetic-input note now apply like every other input.
- **New `mouse_down` / `mouse_up` primitives** — press-and-hold drags the agent
  can inspect mid-flight: grab a clip's trim handle, nudge, screenshot to check
  the frame, release. Wired through safety (medium), permissions (desktop
  scope), post-action screenshots, and the live overlay (Pressing/Releasing).
- **`hold_key` combos with guaranteed release** — holds `'w'` or `'shift+w'`
  for games (walk forward, sprint), duration clamped to 15s, keys released in
  reverse order in a `finally` so an interrupted hold can never leave a stuck
  modifier wrecking the user's session.
- **`scroll` grows `axis` + `modifier`** — `axis: "horizontal"` pans a timeline
  sideways; `modifier: "ctrl"` is held during the scroll (ctrl+scroll = timeline
  zoom in CapCut/Premiere, page zoom in browsers). Amount clamped, modifier
  validated, modifier always released.
- **The model can now SEE all of this** — `left_click_drag`, `hold_key`,
  `scroll`, `double_click`, `right_click`, `mouse_move`, `key_combo`,
  `cursor_position`, `type_with_delay`, `find_on_screen`, and `ocr_image` had
  NO entries in `TOOL_DESCRIPTIONS`, and `get_tool_guidance` only emits
  documented actions — so the planner literally could not discover drag or
  key-hold. All input primitives are now documented with when-to-use guidance
  (timeline clips, trim handles, game movement), and the `computer` wrapper doc
  lists `left_click_drag`/`mouse_down`/`mouse_up`/`hold_key` + scroll axis.
  A regression test pins the guidance so they can't silently vanish again.

### Background agent (input politeness)
- **Keystroke-safety check** — the Calculator keyboard fallback now verifies
  the target window is REALLY foreground (and not minimized) before sending
  any keys; previously a held foreground lock meant the expression was typed
  into whatever window the user had focused, and Ctrl+C read the user's
  clipboard back as the "result".
- **Settle-and-retry read-back** — `uia_click_sequence`'s result read waits
  and re-reads once before concluding a mismatch (the display often hasn't
  repainted 60ms after the last click), so clean InvokePattern runs no longer
  get "corrected" by the focus-stealing keyboard fallback.

### Docs
- New hero demo GIF: a real, pure-InvokePattern run computing 2847×916 in
  21s on Groq Llama-3.3-70b while the Calculator is COVERED by another
  window the entire time — no cursor movement, no screenshots. (Recording
  note: minimizing a freshly-launched UWP app suspends its UIA tree; cover,
  don't minimize.)
- **Fixed silent pixel-click degradation of every "UIA" click.** The
  uiautomation lib defines `GetInvokePattern()` only on its typed control
  subclasses; our tree walks return generic `Control` wrappers, so the call
  raised `AttributeError`, was swallowed, and EVERY uia_click/sequence fell
  back to real-mouse coordinate clicks — which require the window visible and
  silently click whatever covers it (the root cause of the live-run "8 clicks
  ok, display still 0"). A universal `_uia_pattern()` accessor (GetPattern by
  PatternId) restores true InvokePattern delivery: verified live, a chained
  calculation lands on a MINIMIZED Calculator with zero mouse movement. Also
  added a TogglePattern tier for checkboxes/switches.
- **Chained-expression verification** — `uia_click_sequence`'s calculator
  read-back check now evaluates chained input ('12+8=' then '×5=') instead of
  silently skipping verification when the expression contains a mid-sequence
  '='; a wrong display now triggers the keyboard self-correction. Verified
  live on Groq Llama-3.3-70b: (12+8)×5 → verified 100 in 2 actions / 34s
  (June 6 baseline: 86–180s, 9–18 tool failures, zero correct results).
- **Background typing tier** — `uia_type` now tries a UIA `ValuePattern`
  write with read-back verification BEFORE the focus+paste path: on native
  edit controls the text lands with zero focus steal and zero keyboard
  hijack, so the agent can fill fields while the user keeps working. React/
  Electron inputs that desync on value writes are detected by the read-back
  and fall through to the proven focus+paste tier.
- **Input-politeness guard** — every action that hijacks the real keyboard or
  mouse (focus+paste typing, `keyboard_type`, `key_combo`, pixel clicks, OCR
  fallbacks, the Calculator keystroke fallback) now waits — bounded, never a
  deadlock — for the user's hands to pause before acting, and reports when it
  waited. The guard discriminates the agent's own synthetic input from the
  user's via the last-input timestamp, so multi-step runs don't throttle
  themselves. Disable with `ORYNN_INPUT_POLITE=0`.

### Small-model reliability (prompt + loop)
- Desktop system prompt rewritten small-model-first (about half the size):
  a CORE KIT prior, a decision table with canonical examples, a plan-ledger
  protocol (the model restates its numbered plan position every turn, so the
  plan re-enters context and multi-clause goals don't lose their second
  clause), a failure budget (same target failed twice → switch approach;
  three approaches → finish honestly), and an anti-cheat rule (answers must
  be read from the app's UI, never computed in the shell).
- XML fallback prompt pins the exact output format with a canonical example
  (strict one-line JSON, one action per turn) for models whose native tool
  calling hiccups.
- Goal re-anchor: the original goal is re-injected into every 4th desktop
  observation so fast free models stop drifting to the last observation.
- Desktop observation cap raised 1000 → 1600 chars so control menus and
  teaching errors survive truncation.
- Fixed `uia_click_sequence`'s native tool schema omitting `read_result` —
  tool-calling models could never use the verify-in-the-same-call pattern.

### Free-model reliability (desktop control)
- **Control menu on window-ready** — `wait_for_window`, `focus_window`, and app
  launches now attach a "Visible controls" list (real UIA control names) to the
  tool result, so the model picks names off a menu instead of guessing. The
  calculator e2e runs showed free models burning 10+ steps guessing names
  ("Four"/"4"/"digit"/"×") that they could simply have read.
- **Teaching miss errors** — a `uia_find` miss now returns the nearest real
  control names (fuzzy-matched) plus the window's actual interactive controls,
  instead of a bare "no UIA control matched".
- **Zombie-window immunity** — UIA root selection now demotes DWM-cloaked
  frames (suspended/zombie UWP windows that shadow the live app with an
  identical title) and requires real content beyond title-bar chrome; searches
  fall through to the runner-up window on a total miss instead of dying inside
  an empty frame.
- **Finish evidence gate** — a desktop-mode `finish` with zero successful
  desktop actions is bounced once with instructions to do and verify the task
  (kills the "Done." empty-finish failure class seen on small free models);
  a second finish is always allowed through.
- **Keyboard-first guidance** — the desktop prompt now steers the model to one
  keyboard action over click-chains when the app accepts keystrokes, and to
  pick control names from the attached menus.

### Benchmark honesty
- `scripts/benchmark_tasks.py` now records a `route` summary per task and flags
  desktop runs whose answer was computed via shell instead of the app UI
  (`verified_desktop_path` / `route.warning`); BENCHMARKS.md documents the rule.

### Connectors & free-model focus
- **Real API connectors** — weather (Open-Meteo), Wikipedia, Hacker News, GitHub (public repos), and dictionary. Each is a single no-auth API call that returns real structured data, auto-linked with zero setup. This is the surface that stays reliable on a fast free model — one call → real data — unlike the multi-step web-UI driving that derails. Verified live on Groq (London weather, topic summaries, repo stars/issues).
- Reframed the idle dashboard around the reliable free-model use-cases: instant connector answers (weather / explain a topic / trending in tech / check a repo) plus a quick desktop task and run-code.

### Conversation & stream
- Minimal stream: planning/working/reflection chrome collapses into a single calm "Thinking…" indicator with a moving accent shimmer; on completion the working/approval cards fold into "Worked for X" and only the answer text remains.
- Even when the minimal stream suppressed every working card, a finished desktop/coding turn now leaves a quiet "Worked for X" capstone above the answer (a plain chat stays bare).
- The final answer streams in token-by-token (typing reveal) with live markdown formatting.
- Proper markdown rendering — real heading hierarchy (H1–H3), ordered + bullet lists, horizontal rules — in both the web dashboard and the Qt capsule.
- Multi-turn chat: a follow-up message continues the conversation with prior context instead of starting a new one; clicking a continued chat in the sidebar replays the whole thread.
- Sidebar: repeated identical runs collapse into one "×N" row.
- Settings reorganized into General / Permissions / Extensions tabs.

### Agent
- Unified tool surface: the model gets the full tool catalogue (UIA desktop, screen, browser, web research, files, shell) and decides which a task needs, instead of mode-gated tool sets.
- Planning is model-decided: no forced upfront plan for desktop tasks; decomposition is an optional `make_subtasks` tool the model calls only when worthwhile.

### Onboarding & reliability
- Onboarding steers new users to a free **and fast** Groq key (accepts an OpenRouter or Groq key, auto-detected by prefix).
- Groq is now the preferred free provider when its key is set (sub-second vs OpenRouter's 5–15s latency), with a transparent cross-provider fallback to the OpenRouter `:free` chain if Groq is busy/unavailable — fast by default, reliable as backup. A deliberate `DESKTOP_MODEL` opt-in still wins for explicit desktop tasks.
- More persistent chain retry on free-tier rate-limit storms so a transient 429 wave recovers into a (slow) success instead of failing the task.
- During a backoff, the "retrying in Ns…" notice and the stall-watchdog "still working" hint now persist instead of being overwritten by keep-alive heartbeats — a rate-limited task explains the wait rather than silently reading "Thinking".

### Visual polish
- Ambient accent glow enabled, dark default theme, decluttered composer (task options behind a toggle), feed breathing room, and removed the unused 3.2 MB mermaid dependency.

### Docs
- Animated demo GIF as the README hero.

### Dashboard UI
- Codex-inspired redesign: centered idle hero, flat background (no gradient wash), and quiet "reveal-on-hover" chrome so nothing is overloaded.
- Contextual hero that names the active project ("What should we build in <folder>?").
- Session history grouped by working folder as a project tree (folder glyph + nested chats), showing the 5 most recent with a "Show more" expander and folder-scoped search.
- Done-state summary like Codex: a collapsible "Worked for Xm Ys" timeline plus an "N files changed" capstone listing every file the agent created/edited/deleted.
- Hover-revealed message actions: copy the reply and rate it (thumbs wired to the feedback endpoint).
- Replaced the heavy in-app folder browser with a lightweight dropdown (quick folders + native OS "Browse…" dialog).
- Calmer, more professional motion (no blur/throb entrances) and a keyboard focus ring for all controls (`:focus-visible`), honoring `prefers-reduced-motion`.
- Stall watchdog and rate-limit feedback so a running task never sits silently — it surfaces "free models are busy, retrying…" instead of looking frozen.

### Security
- Hardened task identifiers to prevent path-like IDs from reaching task metadata or log file paths.
- Removed API-key prefix/suffix logging and kept task initialization 500 responses generic.
- Reworked dynamic UI rendering for skills, MCP tools, terminal rows, subtasks, and command palette entries so API/model-provided strings are inserted as text, not HTML.

### Reliability
- Added an explicit task kill endpoint and cancellation finalization path so killed tasks end as `cancelled` rather than falling through to max-step failure.
- Cleaned task SSE queues and emitter state on unsubscribe, cancel, kill, and task completion.
- Fixed isolated desktop worker detection so `computer_isolated` keeps cropped isolated screenshots in hierarchical flows.

### Testing
- Added regression tests for task ID containment, generic init errors, log emitter cleanup, kill finalization, and UI injection hardening.
- Added `scripts/cleanup_resources.py` for repeatable low-RAM test hygiene and memory snapshots.

## [1.1.0] - Real-Time Streaming & Discovery Update

### Added
- **Streaming Overhaul**: Low-latency SSE streaming implemented for both the activity log and the main chat panel.
- **Thinking Indicators**: Visual pulsing dots (`...`) in the UI during agent reasoning phases.
- **Coding-First Mode**: High-speed, text-only mode optimized for software engineering.
- **Environment Discovery**: Added `system_info` and `list_directory` tools for dynamic OS/path detection.
- **Enhanced Chat**: Streaming status bubbles and action mini-cards for better feedback.
- **Experimental Vision**:
  - `find_on_screen`: Locates specific images on the display via template matching.
  - `ocr_image`: Full-screen text extraction using Tesseract OCR (requires Tesseract binaries).
  - Integrated scaling logic to ensure accuracy across different screen resolutions.

### Fixed
- **Newline Reliability**: Automatic normalization of literal `\n` characters in file write actions to prevent syntax errors.
- **Cross-Platform Safety**: Standardized `_safe_path` logic for Windows/Unix compatibility.

## [1.0.0] - Production Ready Release

### Added
- **UI Dashboard Rewrite**: Transformed into a 3-panel UI matching modern dashboard quality (Vercel/Linear-inspired) using Inter font and dark theme.
- **Agent Intelligence**: Memory context is now natively prepended to hierarchical planning prompts.
- **Auto Re-planning**: Dynamic generation of a new plan if >2 subtasks consecutively fail.
- **New Tools**:
  - `type_with_delay` for realistic keyboard input.
  - Targeted `scroll` utilizing specific coordinates.
  - Image recognition matching via `find_on_screen`.
  - Clipboard tracking (`get_clipboard`, `set_clipboard`).
  - Desktop popups via `notify`.
- **Robust Endpoints**:
  - `GET /api/health` with exact uptime telemetry.
  - `GET /api/models` explicitly returning activated env-keys.
  - Task management: listing, deletion (cleanup), pause, and resume.
  - Full task history extraction via `GET /api/tasks/{task_id}/log` backed by `.jsonl` appends.

### Fixed
- **Missing Imports**: Correctly scoped `pytesseract` to prevent runtime crashes.
- **Safety Overhaul**: Hard-blocks specifically dangerous shell patterns (`rm -rf`, fork bombs) avoiding accidental system destructions.
- **Timeouts**: Added strict `asyncio.wait_for(timeout=30.0)` around every individual tool execution to avoid hung agents.
- **Infinite Loops**: Hardcap constraint of 50 actions per root task.
- **Async Mismatches**: Verified plugin `playwright` correctly executes inside the async event loop.
- **Error Streams**: Handled graceful shutdown during backend crashes so the SSE client correctly emits an `'error'` signal instead of hanging.
- **ActionType Types**: Synchronized backend Pydantic Enums with the agent handler configurations.

### Changed
- Refactored `MemoryStore` to initialize pure in-memory `_FallbackCollection` automatically if ChromaDB binary dependencies fail.
- OpenRouter/Groq/Google `_chat_*` providers now use 3-attempt exponential backoff for `HTTP 429/500+` stability.
- Screenshot generation dynamically scales to `1280x800` max-resolution before Base64 serialization, saving immense token budgets.
