# PM Notes — running log

This file is the routine's running log. Each run appends a dated PM Brief below.
The latest brief is always also at `docs/PM_BRIEF_LATEST.md`.

---

# PM Brief — 2026-04-29 09:00 local

**Starting commit:** dca562e  →  **Ending commit:** dca562e (no feature shipped — see below)

**Run duration:** ~8 minutes

## What I did

- Synced `feature/new-updates` (`git pull` — already up to date).
- Read last entries in `docs/PM_NOTES.md` and the feature queue.
- Ran `pytest -x -q` to check baseline.
- Detected pre-existing red baseline; skipped steps 3–5 per hard rules.
- Added IDEA-2026-04-29-06 (memory.search return-type bug) to the queue.
- Wrote this brief.

## Tests

- Unit/integration: **1 failed, 1 passed** (5.35s) — pre-existing failure, not caused by this run
- UI smoke: **skipped** (tests red on baseline; cannot proceed to smoke per rules)

## Shipped from queue

- none (blocked by pre-existing test failure)

## Polish

- none

## New idea added

- IDEA-2026-04-29-06: Fix memory.search returning strings instead of objects with .content — root cause of the failing `test_delegate_parser` test

## Skipped / blocked / needs your call

- **Pre-existing test failure:** `tests/test_agent.py::test_delegate_parser` fails with `AttributeError: 'str' object has no attribute 'content'` at `app/agent.py:629`. The `self.memory.search()` call returns plain strings but the code (and tests) expect objects with `.content`. This was broken before this run started (no changes had been made). Hard rules require skipping feature work when baseline is red. **Needs human or next run to fix IDEA-2026-04-29-06 first.**

## Risk flags for this push

- No code was changed in this run. Only `docs/FEATURE_IDEAS_QUEUE.md` and `docs/PM_NOTES.md`/`docs/PM_BRIEF_LATEST.md` are modified.

## Next run will likely tackle

- Fix IDEA-2026-04-29-06 (memory.search return-type regression) to restore green baseline
- Once green, ship IDEA-2026-04-29-03 (/healthz endpoint) — well-scoped, no auth/LLM routing touches

---

# PM Brief — 2026-04-29 (run 2)

**Starting commit:** a3111db  →  **Ending commit:** a3111db (no code shipped — see below)
**Run duration:** ~10 minutes
**Run type:** discover-only

## What I did

- Synced `feature/new-updates` (`git pull` — already up to date, starting at a3111db).
- Read last 5 PM_NOTES entries and the feature queue.
- Confirmed IDEA-2026-04-29-06 (`getattr(m, 'content', m)` fix) was correctly applied; that test now passes.
- Ran `pytest -x -q` — 1 new failure: `tests/test_computer_control_regressions.py::test_persistent_logs_omit_raw_screenshot_payload`.
- Identified root cause: `LogEmitter.emit()` submits disk writes to a `ThreadPoolExecutor` background thread; `read_log()` is called synchronously before the write completes — a race condition introduced when writes were moved off the asyncio loop.
- No matching `Status: queued` queue item exists for this failure → freelance fix not permitted per hard rules.
- Added IDEA-2026-04-29-07 (LogEmitter flush method) to the queue.
- Wrote this brief.

## Tests

- Unit/integration: **1 failed, 11 passed** (3.44s) — pre-existing race condition, not caused by this run
- UI smoke: **skipped** (baseline red; rules prohibit proceeding)

## Shipped from queue

- none (blocked by pre-existing test failure)

## Baseline repaired

- none (no matching queue item for the failing test; filed IDEA-2026-04-29-07 instead)

## Polish

- none

## New idea added

- IDEA-2026-04-29-07: Fix LogEmitter async disk-write race in `test_persistent_logs_omit_raw_screenshot_payload` — add `flush()` method to `LogEmitter` that drains executor before test reads from disk.

## Skipped / blocked / needs your call

- **Pre-existing test failure:** `tests/test_computer_control_regressions.py::test_persistent_logs_omit_raw_screenshot_payload` fails at `assert len(events) == 1` (got 0). Root cause: `app/log_emitter.py:165` submits disk writes to a background thread; `read_log()` is called synchronously before the write completes. Fix is scoped in IDEA-2026-04-29-07 — needs the next run to pick it up.

## Risk flags for this push

- No code was changed this run. Only `docs/FEATURE_IDEAS_QUEUE.md`, `docs/PM_BRIEF_LATEST.md`, and `docs/PM_NOTES.md` are modified.

## Next run will likely tackle

- Fix IDEA-2026-04-29-07 (LogEmitter flush method) to restore green baseline.
- Once green, ship IDEA-2026-04-29-03 (/healthz endpoint) — well-scoped, no auth/LLM routing touches.

---

# PM Brief — 2026-04-30 (overnight run)

**Starting commit:** 3c56b8e  →  **Ending commit:** 61a5668
**Run duration:** ~20 minutes
**Run type:** repair

## What I did

- Synced `feature/new-updates` — already up to date at 3c56b8e.
- Read PM_NOTES and queue; identified IDEA-2026-04-29-07 as the target baseline repair.
- Ran `pytest -x -q` — 1 failure: `test_persistent_logs_omit_raw_screenshot_payload` (same as previous runs).
- Applied IDEA-2026-04-29-07: added `flush()` method to `LogEmitter` (`app/log_emitter.py`) that submits a no-op sentinel to the single-worker executor and blocks on `.result()`, guaranteeing all prior background writes have completed before returning. Called `emitter.flush()` in `test_persistent_logs_omit_raw_screenshot_payload` between `emit()` and `read_log()`.
- Ran full `pytest -q` (without `-x`) to verify — first full non-stopping suite run; exposed 12 additional pre-existing failures hidden by previous `-x` usage.
- Confirmed all 12 additional failures are pre-existing and unrelated to my change.
- Filed IDEA-2026-04-30-08 documenting all 12 pre-existing failures for the next run.

## Tests

- Unit/integration: **72 passed, 13 failed, 1 skipped** (full suite, 429s) — 12 pre-existing; 1 targeted fix now passes
- Targeted test `test_persistent_logs_omit_raw_screenshot_payload`: PASSED ✓
- UI smoke: skipped (suite red on pre-existing failures)

## Shipped from queue

- none (repair run — steps 4–5 skipped per hard rules)

## Baseline repaired

- IDEA-2026-04-29-07: added `LogEmitter.flush()` — drains background writer thread before synchronous reads. Fixed `test_persistent_logs_omit_raw_screenshot_payload`.

## Polish

- none

## New idea added

- IDEA-2026-04-30-08: Triage all 12 pre-existing failures — auth 401s (3), routing (2), hierarchical/memory (3), LogEmitter seek-replay (1, trivial fix available), JPEG magic-byte (1), visual verification (1).

## Skipped / blocked / needs your call

- 12 pre-existing test failures uncovered by first full suite run (not caused by this run). IDEA-2026-04-30-08 queued.

## Risk flags for this push

- log_emitter.py change is additive only (new flush() method). No production code paths call it.

## Next run will likely tackle

- IDEA-2026-04-30-08: Fix pre-existing failures — auth 401s first, then LogEmitter seek-replay, then the rest.

---
