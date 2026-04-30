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

### [IDEA-2026-04-30-08] Fix pre-existing test suite failures exposed by full (non -x) run

- **Source app / link:** `tests/test_security.py:33,60,76`, `tests/test_fast_path.py:49,88`, `tests/test_hierarchical.py:23,44,70`, `tests/test_project_folder_runtime.py:44,86,102`, `tests/test_vision_loop.py:28`, `tests/test_visual_verification.py:20`
- **Why it fits Ai_computer:** First full non-`-x` suite run (2026-04-30) revealed 12 pre-existing test failures hidden because previous runs stopped at the first failure. These are real bugs: auth endpoints returning 401, routing assertions never true, memory.search result `m.content` access, JPEG magic-byte mismatch, and LogEmitter seek-replay race.
- **Scope (this PR only):** Fix the authentication failures first (3 tests in `test_security.py` return 401 — likely a test fixture API key env-var propagation issue). After auth is green, triage fast-path routing and hierarchical failures. For the LogEmitter seek-replay test (`test_project_folder_runtime.py:102`): add `emitter.flush()` calls before each `read_log()` — flush() already exists from IDEA-2026-04-29-07.
- **Acceptance criteria:** All 12 previously-failing tests pass. Full `pytest -q` (no `-x`) is green.
- **Out of scope:** New feature work; changes to app/safety.py or auth/security middleware beyond what the test fixtures need.
- **Status:** queued

