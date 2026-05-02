# Feature ideas queue (autopilot)

**Discovery job** appends new sections. **Main autopilot job** picks **one** `Status: queued` item when tests are green.

Convention:

- Use a unique `IDEA-...` id per row block.
- Keep each idea **one small PR**; if it is huge, split into multiple IDEA ids.
- Main job updates **Status** to `in_progress` → `done` (or `blocked` with reason).

---

## Template (copy for new ideas)

### [IDEA-YYYY-MM-DD-01] Short title

- **Source app / link:** (optional)
- **Why it fits Ai_computer:**
- **Scope (this PR only):**
- **Acceptance criteria:**
- **Out of scope:**
- **Status:** queued

---

## Queued / history

_(Discovery cron will append below. You can seed items manually.)_

### [IDEA-2026-04-29-01] Persist last-used mode across reloads

- **Why it fits Ai_computer:** Users reload the UI often during long agent runs; losing the selected mode (Coding/Browser/Desktop) is friction.
- **Scope (this PR only):** Save selected mode to localStorage on change; restore on page load. Fall back to auto-detect if absent.
- **Acceptance criteria:** Refresh the page after picking Browser mode → Browser is still selected. Unit/UI smoke test covers the round-trip.
- **Out of scope:** Persisting other UI state (model, API key prefs).
- **Status:** queued

### [IDEA-2026-04-29-02] Copy-task button on completed runs

- **Why it fits Ai_computer:** Re-running or tweaking a previous task is currently retype-from-memory; a one-click copy speeds iteration.
- **Scope (this PR only):** Add a small "↻ Copy task" button on each finished run card that fills the input box with the original goal text.
- **Acceptance criteria:** Button appears only on terminal-state runs; click populates input and focuses it. Playwright smoke test added.
- **Out of scope:** Editing/forking mid-run, history search.
- **Status:** queued

### [IDEA-2026-04-29-03] /healthz endpoint with provider checks

- **Why it fits Ai_computer:** Currently no quick way to verify which LLM providers are reachable / keys valid before kicking off a run.
- **Scope (this PR only):** Add `GET /healthz` that returns `{server: ok, providers: {openrouter: ok|missing_key|unreachable, ...}}`. Cache results for 30s.
- **Acceptance criteria:** Hitting /healthz with a missing key returns `missing_key` for that provider; with a valid key returns `ok`. Test added with mocked HTTP.
- **Out of scope:** Surfacing this in the UI (separate idea).
- **Status:** queued

### [IDEA-2026-04-29-04] Run duration + token-cost badge on each run card

- **Why it fits Ai_computer:** Helpful to see at a glance how long a run took and roughly what it cost; encourages tighter prompts.
- **Scope (this PR only):** Compute wall-clock duration and approximate cost (token counts × model price table) and render as a small badge on each run card.
- **Acceptance criteria:** Free-tier OpenRouter runs show "$0.00 · 23s"; paid models show estimated cost. Unit test on the cost calculator.
- **Out of scope:** Aggregate analytics, daily/weekly reports.
- **Status:** queued

### [IDEA-2026-04-29-05] Auto-pause on repeated identical tool calls

- **Why it fits Ai_computer:** Agents sometimes loop calling the same tool with the same args; today the only escape is manual Pause.
- **Scope (this PR only):** Detect ≥3 identical consecutive tool calls (same name + args hash) and auto-pause with a banner explaining why.
- **Acceptance criteria:** Synthetic test feeding 3 duplicates triggers pause; 2 does not. Banner visible in UI smoke.
- **Out of scope:** Smarter cycle detection across non-adjacent calls.
- **Status:** queued

### [IDEA-2026-04-29-06] Fix memory.search returning strings instead of objects with .content

- **Source app / link:** `app/agent.py:629`, `tests/test_agent.py::test_delegate_parser`
- **Resolution:** Made lines 629/633 tolerant of both objects-with-.content and plain strings via `getattr(m, 'content', m)`. Test green.
- **Status:** done

### [IDEA-2026-04-29-07] Fix LogEmitter async disk-write race in test_persistent_logs_omit_raw_screenshot_payload

- **Source app / link:** `app/log_emitter.py:165`, `tests/test_computer_control_regressions.py::test_persistent_logs_omit_raw_screenshot_payload`
- **Why it fits Ai_computer:** The test fails because `emit()` submits disk writes to a `ThreadPoolExecutor` background thread, then `read_log()` is called synchronously before the write completes — an inherent race condition. Persistent log reads return 0 events instead of 1.
- **Scope (this PR only):** Add a `flush()` method to `LogEmitter` that drains all pending writes by submitting a sentinel task to the executor and calling `.result()` on it. Update `test_persistent_logs_omit_raw_screenshot_payload` to call `emitter.flush()` between `emit()` and `read_log()`. No other tests or callers change.
- **Acceptance criteria:** `pytest tests/test_computer_control_regressions.py::test_persistent_logs_omit_raw_screenshot_payload` passes. Full suite green.
- **Out of scope:** Changing the async write design for production paths; adding flush calls outside the test.
- **Status:** done

### [IDEA-2026-04-30-08] Master ticket: 12 pre-existing failures (split into 08a–08f below)

- **Source:** First full non-`-x` suite run (2026-04-30) surfaced 12 pre-existing failures hidden by `-x`.
- **Status:** split (do not work this directly — pick a sub-ticket)

### [IDEA-2026-04-30-08a] Fix LogEmitter seek-replay race in test_project_folder_runtime

- **Source app / link:** `tests/test_project_folder_runtime.py::test_log_emitter_seek_replay_uses_binary_offsets_for_utf8`
- **Resolution:** Added `emitter.flush()` before `read_log()` in the test. Test now passes.
- **Status:** done

### [IDEA-2026-04-30-08b] Fix auth 401 failures in test_security

- **Source app / link:** `tests/test_security.py:33,60,76`
- **Resolution:** Root cause was `load_dotenv(override=True)` in `main.py:3` clobbering the monkeypatched `AGENT_API_KEY` during `importlib.reload()`. Fix: `monkeypatch.setattr(m, "API_KEY", "token123")` after reload in `_client()`. All 7 security tests pass.
- **Status:** done

### [IDEA-2026-04-30-08c] Fix hierarchical/memory `.content` AttributeErrors

- **Source app / link:** `tests/test_hierarchical.py:23,44,70`
- **Partial resolution (line 70 — test_phase_updates_emit_progress):** Test mocked `asyncio.sleep` to instant, so real elapsed time never reached the 1s heartbeat threshold. Fix: pass `heartbeat_seconds=0` to `_run_with_phase_updates` in the test. Test now passes.
- **Remaining (lines 23,44 — test_hierarchical_success, test_hierarchical_retry):** Root cause is that tests check `s.memory.search("task_outcome")` expecting items with `"Outcome: True"`, but production code never stores this. `summarize_session()` stores `session_summary` with "Completed successfully". Expected behavior was never implemented. Needs human.
- **Status:** needs_human (lines 23,44 remain; line 70 fixed)

### [IDEA-2026-04-30-08d] Fix fast-path routing `call_llm_called` assertion failures

- **Source app / link:** `tests/test_fast_path.py:49,88`
- **Resolution:** Tests called `run_task()` without `mode="computer"`, so the hierarchical/fast-path block (`if mode in ("computer", "computer_isolated")`) was never entered. Fix: added `mode="computer"` and mocked `_capture_screenshot_b64` in both tests. Both tests now pass.
- **Status:** done

### [IDEA-2026-04-30-08e] Fix JPEG magic-byte / vision-loop screenshot decoding

- **Source app / link:** `tests/test_vision_loop.py:28`, `tests/test_visual_verification.py:20`
- **Resolution (test_vision_loop):** `_capture_screenshot_b64` returns a data URL (`"data:image/jpeg;base64,..."`) but the test was calling `base64.b64decode()` on the full data URL string, getting garbage bytes. Fix: strip prefix with `.split(",", 1)[1]` before decoding. Test passes.
- **Resolution (test_visual_verification):** Same root cause as IDEA-08c — `memory.search("task_outcome")` returns empty; `"Outcome: True"` is never stored. Needs human intervention.
- **Status:** done (vision_loop fixed; visual_verification → needs_human, same as 08c)

### [IDEA-2026-04-30-08f] Fix remaining project-folder-runtime failures

- **Source app / link:** `tests/test_project_folder_runtime.py:44,86`
- **Resolution:** Same auth issue as IDEA-08b — `load_dotenv(override=True)` clobbered monkeypatched key. Fixed by `monkeypatch.setattr(m, "API_KEY", "token123")` in the project_folder_runtime `_client()` fixture. Both tests pass.
- **Status:** done

### [IDEA-2026-04-30-09] Self-host mermaid.js (remove jsdelivr CDN)

- **Source:** `static/index.html:10` — `<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js">`
- **Why it fits Ai_computer:** Hard CDN dependency means the UI breaks on any offline / firewalled / air-gapped run. The whole product premise (run anywhere) is undermined by one external script tag.
- **Scope (this PR only):** Vendor `mermaid@10.9.1/dist/mermaid.min.js` into `static/vendor/mermaid.min.js`, update the script tag, add the file to git. ~2 LOC change in HTML + one vendored JS file (~3 MB but it's static).
- **Acceptance criteria:** `static/index.html` has no `cdn.jsdelivr.net` references. UI loads with internet disconnected. UI smoke test still passes.
- **Out of scope:** Vendoring other CDN assets (Google Fonts) — separate IDEA if needed.
- **Status:** queued

### [IDEA-2026-04-30-10] Persist AGENT_API_KEY across server restarts

- **Source:** `app/main.py:21` — `API_KEY = os.environ.get("AGENT_API_KEY") or secrets.token_hex(32)`
- **Why it fits Ai_computer:** When `AGENT_API_KEY` is unset, every restart generates a new key, silently invalidating any existing CLI/integration that stored the previous one. Users get unexplained 401s after a routine reboot.
- **Scope (this PR only):** On startup, if `AGENT_API_KEY` env var is unset, check for `workspace/.api_key` file. Use it if present; otherwise generate, write to that file (mode 600), use it. Log the file path on first generation. ~15 LOC.
- **Acceptance criteria:** Restart server with no env var → same API key as previous run. Setting the env var still wins. New unit test covers both paths.
- **Out of scope:** Key rotation, multi-key support.
- **Status:** queued

### [IDEA-2026-04-30-11] Streaming token + cost counter in UI

- **Source:** `static/index.html` (run cards), `app/agent.py` SSE event emission
- **Why it fits Ai_computer:** Today users can't see how many tokens a run consumed or what it cost until after — Cursor/Aider/OpenHands all show this live. Encourages tighter prompts and helps users stay within free-tier limits.
- **Scope (this PR only):** Emit a new SSE event `usage_update` with `{prompt_tokens, completion_tokens, cost_usd}` after each LLM call. Render a small live-updating badge in the run card ("12.4k tok · $0.03"). Cost = sum across calls; use a hardcoded provider price table in `app/providers.py`.
- **Acceptance criteria:** Free-tier OpenRouter run shows `$0.00 · 23s`; paid model shows nonzero. Unit test on the cost calculator. UI smoke verifies badge updates mid-run.
- **Out of scope:** Aggregate dashboard, daily/weekly cost rollups, exporting usage data.
- **Status:** queued

### [IDEA-2026-04-30-12] Cache /api/mcp instead of re-initializing on every GET

- **Source:** `app/main.py:432` — `await mcp_manager.initialize_default_servers(...)` runs on every GET
- **Why it fits Ai_computer:** Re-initializing MCP servers on every UI poll is wasteful (the UI may poll `/api/mcp` periodically). `initialize_default_servers` is presumably idempotent but still does work each time.
- **Scope (this PR only):** Remove the re-init call from the GET handler — rely on the lifespan-startup init. If the manager isn't ready yet, return `{"servers": [], "initializing": true}` so the UI can retry. ~5 LOC.
- **Acceptance criteria:** `GET /api/mcp` returns in <50ms after startup. Existing test for `/api/mcp` still passes; new test asserts no re-init happens on repeated GETs.
- **Out of scope:** Changing how `mcp_manager` itself initializes.
- **Status:** queued

### [IDEA-2026-05-01-01] Limit TextEditorTool undo history to prevent unbounded memory growth

- **Source app / link:** `app/text_editor.py:49,67` — `str_replace`/`insert` store entire pre-edit file text in `self._history` per path with no bounds
- **Why it fits Ai_computer:** Text editor tool is used for file modifications; on large files or long editing sessions, `self._history` can grow unbounded (stores full file text for every edit). This wastes memory and has no practical limit.
- **Scope (this PR only):** Add a max history limit (e.g., 50 or 100 entries total across all files, or per-file cap of ~10 undo levels). Trim oldest history when limit exceeded. ~10–15 LOC in `text_editor.py`.
- **Acceptance criteria:** After exceeding the limit, oldest history entries are dropped; `undo_edit` still works for recent edits. Unit test verifies cap is enforced. No change to external API or behavior for within-limit cases.
- **Out of scope:** Changing undo semantics, adding redo support, or persisting history across restarts.
- **Status:** queued
