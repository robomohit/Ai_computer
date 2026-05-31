# PM Brief — 2026-05-31 (automated run)

**Starting commit:** `d44e6ec`  →  **Ending commit:** `d16bef6`
**Run duration:** ~45 min  |  **LOC budget used:** ~117/200
**Run type:** mixed (3 features shipped, 1 pre-impl discovered)

## What I did
- Synced `feature/new-updates` — already up to date at d44e6ec (user's UIA/click/OCR commits).
- Read last 5 PM briefs, standing policy, and RESEARCH_NOTES (outer repo, latest: 2026-05-31 triage).
- Ran full `pytest -q` — **243 passed, 1 skipped, 0 failed** baseline (user's 5 commits added 33 new tests since last PM run).
- UI smoke: GET / → 200, server killed cleanly, no orphan processes.
- Linear survey: 0 In Progress, 0 blocked. Only real shippable Todo: AI-13 (needs browser-tab infra, skipped prior run). Promoted 4 Backlog items.
- Shipped AI-32: usage_update in hierarchical plan path.
- Shipped AI-31: task_id in git auto-commit message.
- Shipped AI-27: background session-token pruning.
- Discovered AI-30 (anchor automation.json) is pre-implemented (workspace_state_path already respects AI_COMPUTER_WORKSPACE); marked Done.
- Board hygiene: all issues < 12 days old, no stale/blocked items, no file-gone refs.
- Filed AI-33 (SSE backpressure, Backlog).

## Tests
- Unit/integration: **247 passed, 1 skipped, 0 failed** (28.5s) — Δ +4 from baseline
- UI smoke: GET / → 200, no orphan processes

## Repaired
- none (baseline was already green)

## Shipped
- **AI-32:** emit usage_update SSE when hierarchical plan completes — was missing from the hierarchical path (lines ~1271-1273 in agent.py) that returns early without entering the streaming ReAct loop where usage_update was already emitted. 1 LOC + 1 test.
- **AI-31:** include task_id[:8] in git auto-commit message body — `_git_commit_file()` now accepts `task_id=""` and appends `task: {id[:8]}` to the message body. 4 LOC + 2 tests.
- **AI-27:** background session-token pruning loop — `_prune_sessions_loop()` started in `_lifespan`, cancelled at shutdown alongside telegram/discord. 9 LOC + 1 test.

## Polished (unsolicited)
- none

## New issues filed
- **AI-33:** SSE asyncio queue backpressure for slow/mobile clients — `_stream_chunk()` has no asyncio.Queue throttling; unbuffered on slow networks. ~120 LOC, Medium priority, Backlog. Source: 2026-05-31 research triage.

## Decisions I made (and why)
- **AI-30 marked pre-implemented:** Issue was filed when `automation.py` used a bare `"automation.json"` literal. Current code already uses `workspace_state_path(_REGISTRY_FILE)` which respects `AI_COMPUTER_WORKSPACE`. My attempt to add `_registry_path()` broke 5 automation tests by changing the fallback path from `./automation.json` to `~/.config/ai_computer/automation.json` — tests relied on the CWD behavior. Reverted and marked Done with a comment explaining.
- **Promoted Backlog items instead of attempting AI-13:** All real Todo issues are needs-design. AI-13 (Private Context Bridge) was explicitly skipped prior run for lacking browser-tab infrastructure. The Backlog items (AI-32, AI-31, AI-27) had clear acceptance criteria, small scope, and directly touched code reviewed this run.

## Skipped / blocked / NEEDS HUMAN
- **AI-13:** Private Context Bridge — skipped again (prior run's judgment held: requires browser-tab reading infrastructure not yet in codebase). Will need design pass before implementation.
- **AI-5, AI-14, AI-18:** all needs-design → skipped per contract.

## Risk flags for this push
- `app/agent.py` AI-32: additive single line at hierarchical-path completion; no production path removed.
- `app/agent.py` AI-31: `_git_commit_file` signature change adds optional `task_id=""` param — all existing callers get default behavior; updated existing mocks in tests.
- `app/main.py` AI-27: `_prune_sessions_loop` is a 300s-sleep loop; negligible overhead. Shutdown cancel is in the existing task cancel loop.

## Health snapshot
- Full suite: **247 passed, 1 skipped, 0 failed**  (Δ vs last run: +37 passed — 33 from user commits, 4 from this run)
- Open Todo issues: 8 (4 real: AI-5/14/18 needs-design + AI-13; 4 Linear placeholders)  (Δ: ±0)
- In Progress / blocked / needs-design: 0 / 0 / 3
- Lines shipped this run: ~117  /  Last 7 runs avg: ~145
- Trend: **healthy** — suite green, 3 backlog items closed, user's UIA commits cleanly integrated
- Haiku research last contributed: 2026-05-31 (outer repo)

## Next run will likely tackle
- **AI-8:** Watch & Act slice 2 — filesystem-watch trigger (Backlog → promote, ~100 LOC, slice 1 already shipped)
- **AI-13:** Private Context Bridge — survey browser-tab reading capability (audit `app/tools.py` browser actions, decide if scope is tractable)
