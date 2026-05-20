# PM Brief — 2026-05-20 11:30 local
**Starting commit:** e212ce6  →  **Ending commit:** 61fc751
**Run duration:** ~100 minutes (test suite runs 6 min each)  |  **LOC budget used:** ~182/200
**Run type:** feature (AI-16 shipped)

## What I did
- Synced `feature/new-updates` — already up to date at e212ce6 (5 commits ahead of origin from prior runs).
- Read PM_NOTES.md, ROUTINES.md (queue migrated to Linear today), and 2026-05-20 Haiku research notes.
- Ran full `pytest -q` — **155 passed, 1 skipped, 0 failed** baseline (green).
- Confirmed queue is now in Linear (`Ai_computer` team, `AI Computer roadmap` project). Loaded Todo issues; picked highest-priority unblocked item without `needs-design`: AI-16.
- Shipped AI-16: chain-level retry for exhausted free-model fallback chain.
- Moved AI-5 (pluggable coding backends) from In Progress → Todo; it has `needs-design` label and was auto-set In Progress by the migration, not by the build routine.
- Queue hygiene: all issues < 1 day old (migrated today), no stale/blocked/obsolete items.
- Discovered AI-25: raise `ValueError` on unknown backend type.
- Pushed branch; updated Linear (AI-16 → Done, AI-25 filed, AI-5 → Todo).

## Tests
- Unit/integration: **158 passed, 1 skipped, 0 failed** (+3 from new chain-retry tests)
- UI smoke: skipped (no static/ changes this run; backend-only change verified by unit tests)

## Repaired
- none (baseline was already green)

## Shipped from queue
- **AI-16:** Chain-level retry for exhausted free-model fallback chain — `_CHAIN_RETRY_MAX=2` + `_CHAIN_RETRY_BACKOFFS=[10,30]`; `stream_chat_with_tools` refactored into public wrapper (chain retry) + `_stream_chat_with_tools_single` (inner one-shot generator); emits `{"type":"provider_info","retrying":true,"message":"All free models are busy — retrying in Xs…"}` before each backoff; raises `RuntimeError("All free models are currently busy. Please try again in a moment.")` after exhaustion; non-rate-limit errors propagate immediately; sync `_chat_openrouter` path also wrapped. 3 new tests.

## Polished (unsolicited)
- none

## New idea added
- **AI-25:** Raise `ValueError` on unknown backend type in `BackendRegistry._load()` (~5 LOC, Low priority). Source: 2026-05-20 research scan of `app/coding_backends.py`.

## Decisions I made (and why)
- **Refactored `stream_chat_with_tools` into wrapper + inner method** rather than wrapping the 140-line model-iteration for-loop in an outer loop (which broke indentation in a test edit). The public method does chain retry via `async for event in self._stream_chat_with_tools_single(...): yield event`. Clean, testable, and the interface is unchanged.
- **Chain retry only on 429 errors** — non-rate-limit HTTP errors (e.g. 400) propagate immediately. Checked via `isinstance(e, httpx.HTTPStatusError) and e.response.status_code in (402, 429)`.
- **Cap: 10s + 30s backoff (40s total)** — keeps total wait under 1 minute for a three-attempt chain. Short enough to be usable; long enough for rate-limit windows to reset.
- **AI-5 moved back to Todo** — it was auto-set to In Progress during the Linear queue migration today but has `needs-design` label. Per contract, `needs-design` issues are skipped; moved back to Todo.

## Skipped / blocked / NEEDS HUMAN
- **AI-5 (Connectors: pluggable coding backends):** Has `needs-design` label + description says "Slice 1 already shipped." Issue may need to be split further or the label removed after a design review.

## Risk flags for this push
- `app/providers.py`: `stream_chat_with_tools` now delegates to `_stream_chat_with_tools_single`. Any code that monkey-patches `stream_chat_with_tools` (mocks in test_computer_control_regressions.py, test_project_folder_runtime.py) replaces the whole public method — unaffected. Test that calls `provider.stream_chat_with_tools` in test_providers.py now exercises the wrapper — correct.
- Chain retry adds up to 40s extra latency if all models 429 twice. Acceptable tradeoff vs raw error.

## Health snapshot
- Full suite: **158 passed, 1 skipped, 0 failed**  (Δ vs last run: +3 passed / ±0 failed)
- Open Todo IDEAs in Linear: ~13 Todo, 1 Backlog group (Watch & Act + Connectors)  (Δ: -1 shipped AI-16, +1 new AI-25)
- Blocked / stale / needs_human IDEAs: 0 blocked; 2 needs-design in Todo (AI-14, AI-18)
- Lines shipped this run: ~182  /  Last 7 runs avg: ~95
- Trend: **healthy** — suite green, high-priority resilience feature shipped, queue now in Linear
- Haiku research last contributed: 2026-05-20

## Next run will likely tackle
- **AI-17:** Stream reasoning + tool-call inputs token-by-token (High priority, free-model-safe, ~50-80 LOC)
- **AI-24:** Copy button on turn-step-output blocks (Low priority, quick win, ~20 LOC)
