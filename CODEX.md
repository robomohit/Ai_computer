# AI Computer

AI Computer is a FastAPI-based autonomous agent app with a browser UI. The backend lives in `app/` and includes task orchestration (`agent.py`), provider/planner integration (`providers.py`), tool execution (`tools.py`), permissions/safety (`permissions.py`, `safety.py`), and memory/logging. The frontend is a single-page app in `static/index.html`. Test coverage lives under `tests/`, with a few local-server smoke tests in the repo root.

## Backlog

- Improve backend responsiveness under long-running tool actions and permission waits.
- Add stronger tests for provider error payloads, permission flows, and long-running commands.
- Add clearer UI state for planning, reflecting, evaluating, and waiting on permission.
- Improve task lifecycle observability with better logs and structured error reporting.
- Consider lightweight frontend smoke coverage if a safe local harness exists.

## Known issues / debt

- Some tool methods are synchronous and may block async task execution if not isolated carefully.
- The local-server smoke tests are skip-based and do not fully validate UI flows automatically.
- There are still several broad exception handlers that reduce debugging clarity.
- The frontend is a single large HTML file, which makes targeted UI changes a bit brittle.

## Session log

### Iteration 1

Goals:
- Prevent blocking tool execution from stalling the FastAPI/agent event loop.
- Add regression coverage proving long-running blocking tools do not freeze concurrent async progress.

Acceptance criteria:
- Long-running sync tool actions run off the event loop.
- Existing tests stay green.
- A new test covers the non-blocking execution path.

Plan:
- Files: `app/tools.py`, `tests/test_new_actions.py`
- Tests to add/update: add an async regression test around `run_action()` with a blocking tool method.
- Verification commands: `pytest`, `python -m compileall app`

What I changed:
- Moved synchronous standard tool handlers in `app/tools.py` onto `asyncio.to_thread()` so blocking shell/file/network/process work does not run on the event loop.
- Also offloaded synchronous plugin handlers to threads for consistency.
- Added a regression test in `tests/test_new_actions.py` proving a blocking `run_command` call does not stall concurrent async progress.

Checks run:
- `pytest tests\test_new_actions.py tests\test_agent.py -q` -> passed
- `python -m compileall app` -> passed
- `pytest` -> passed (`36 passed, 4 skipped`)

Remaining notes:
- This addressed the most serious backend responsiveness risk observed during live smoke testing.
- Broader exception cleanup remains possible later, but it is lower priority now that blocking tool execution is isolated.

### Iteration 2

Goals:
- Harden task creation so duplicate task IDs do not corrupt in-memory task state.
- Validate task mode values at the API boundary instead of accepting arbitrary strings.

Acceptance criteria:
- Creating a task with an existing live/persisted ID returns a clear conflict error.
- Invalid `mode` values are rejected by request validation.
- Tests cover both behaviors and the suite remains green.

Plan:
- Files: `app/main.py`, `tests/test_agent.py`
- Tests to add/update: duplicate task creation conflict, invalid mode validation.
- Verification commands: `pytest`, `python -m compileall app`

What I changed:
- Tightened `TaskIn.mode` in `app/main.py` to `Literal["auto", "coding", "computer", "computer_use"]`.
- Added duplicate task ID checks in `POST /api/tasks` so existing active or completed IDs return `409 Conflict` instead of silently overwriting in-memory task state.
- Added API tests in `tests/test_agent.py` for duplicate active task IDs and invalid task modes.

Checks run:
- `pytest tests\test_agent.py -q` -> passed
- `python -m compileall app` -> passed
- `pytest` -> passed (`38 passed, 4 skipped`)

Remaining notes:
- Root smoke tests are still skip-based because they depend on a live local server.
- Future work could standardize API error payloads and tighten some broad exception handlers, but those are incremental polish rather than urgent fixes.

### Early stop

Stopped after Iteration 2.

Reason:
- The repo is green, the highest-value hardening items from this session are complete, and the remaining candidate changes are lower-value or more invasive than is justified for another safe iteration right now.
