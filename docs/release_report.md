# AI Computer Production Hardening Release Report

## Scope
- Branch: `cursor/production-hardening-4ba1`
- Base: `feature/new-updates`
- Focus: security, task lifecycle reliability, desktop isolated behavior, UI injection hardening, low-RAM test hygiene, and free-model defaults/fallback validation.

## Baseline and inventory
- OS: Linux 6.12.58+ x86_64.
- Python: 3.12.3 (`python3`; no `python` shim).
- Memory: about 15.3 GB available during validation.
- Default pytest catalog: 51 tests in `tests/`.
- Heavy/live tests remain explicit root-level scripts (`e2e_test.py`, `test_model.py`, `test_delegation.py`) and are excluded by `pytest.ini`.
- Optional desktop dependency: `pywin32>=306; platform_system == "Windows"` remains Windows-only; Linux test run validates graceful missing-helper behavior.

## Bug ledger
| ID | Severity | Root cause | Fix | Regression evidence |
|---|---|---|---|---|
| PROD-001 | High | API-controlled task IDs were unconstrained and used in task/log paths. | Added strict 1-128 char ID validation and log path rejection. | `test_task_id_rejects_path_traversal`, `test_log_emitter_rejects_path_like_task_ids_and_cleans_queues` |
| PROD-002 | High | `computer_isolated` workers detected isolation only for `mode == "computer"`. | Treat `computer_isolated` or resolved isolated HWND as isolated. | Existing isolated-mode regressions plus static desktop finish coverage |
| PROD-003 | High | Killed tasks could fall through as max-step failures; cancel cleanup was incomplete. | Added kill endpoint/path, cancelled finalization, CancelledError handling, pause kill checks, and log cleanup. | `test_killed_task_finalizes_as_cancelled_not_max_steps` |
| PROD-004 | Medium | Startup/API errors exposed too much detail. | Removed API-key prefix/suffix startup print and return generic create-task 500 detail. | `test_create_task_internal_error_does_not_leak_details` |
| PROD-005 | Medium | SSE queue bookkeeping retained empty per-task entries. | Prune empty queues on unsubscribe and cleanup terminal tasks. | `test_log_emitter_rejects_path_like_task_ids_and_cleans_queues` |
| PROD-006 | High | UI rendered API/SSE/model-derived strings through `innerHTML`. | Replaced dynamic skills, MCP, terminal, subtask worker tag, and command palette rendering with DOM/textContent APIs. | `tests/test_ui_static_hardening.py` |
| PROD-007 | Medium | Test command assumed `python` exists. | Use `sys.executable` for the command execution regression. | `tests/test_new_actions.py` |
| PROD-008 | Low | Runtime artifacts from tests were unignored. | Ignore `tasks/*.json`, `workspace/logs/`, screenshots, and tmp files. | Final git/ignored artifact sweep |

## Security report
- Verified `/api/config` does not return raw API keys.
- Verified query-token SSE auth is rejected.
- Verified task ID traversal/path-like IDs are rejected before task/log filesystem use.
- Verified create-task internal failures return a generic message without exception detail.
- Verified dynamic UI sections no longer interpolate untrusted strings as HTML.
- Verified persistent screenshot logs omit raw base64 payloads.
- Remaining risks: unauthenticated session bootstrap is still product behavior; public `/api/skills`, `/api/mcp`, and `/api/models` remain public metadata endpoints. Consider scoped sessions or admin protection if this server is exposed beyond localhost.
- Non-goals: live CVE remediation and real provider secret rotation were not performed.

## Reliability and lifecycle report
- Desktop structured finish regression still verifies immediate `done` finalization without reflection retry loops.
- Kill/cancel now finalizes deterministically as `cancelled`, emits a terminal event, and cleans log-emitter state.
- Approval and permission timeout tests remain present and passing.
- Streaming fallback tests validate OpenRouter free-model fallback on 429 and XML timeout handling.
- SSE queue state is bounded after unsubscribe/cleanup.

## Performance and RAM report
- Added `scripts/cleanup_resources.py` for explicit cleanup and RAM probes around suites.
- Final consolidated default suite:
  - Before: `mem_available_kb=15375088`
  - After: `mem_available_kb=15368480`
  - Result: `51 passed in 10.34s`
- Targeted regression suite:
  - Before: `mem_available_kb=15380020`
  - After: `mem_available_kb=15358100`
  - Result: `24 passed in 2.66s`
- Persistent logs already omit screenshot base64; this remains covered.
- Remaining hotspots: live browser/desktop E2E can still consume Chromium/GUI resources and should be run separately with cleanup between scenarios.

## Free-model defaults and fallback
- README documents OpenRouter free tier as recommended.
- Provider default remains `openrouter/nvidia/nemotron-3-super-120b-a12b:free`.
- `/api/tasks` auto-selects free OpenRouter models when `OPENROUTER_API_KEY` exists, including Qwen coder for coding mode.
- Regression coverage validates OpenRouter streaming fallback from one free model to another on HTTP 429.

## Test report
- Collected default tests: 51.
- Targeted high-risk run: 24 passed.
- Sequential file-by-file default run: 51 passed across all `tests/test_*.py` files.
- Final consolidated run: 51 passed in 10.34s.
- Heavy/live tests not run: root-level E2E/provider scripts require an already running local server and real provider/browser/desktop environment.

## Manual checks not completed in cloud
- Real Windows desktop torture scenarios: Calculator 2+2=4 and Notepad save/edit require a Windows desktop session.
- Full desktop `computer` screenshot + active-window description requires a GUI session.
- Real public website browser extraction/rate-limit behavior requires live browser/network E2E.
- Provider 429 storms were simulated in tests; broader live provider quality/latency/cost comparisons were not performed.

## Go/no-go recommendation
- Recommendation: Go for the covered API/security/lifecycle/UI hardening scope.
- Confidence: 0.82.
- Residual risk: Windows-only desktop behavior and live browser/provider chaos scenarios still need environment-backed E2E before a broad public release.
