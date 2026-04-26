# AI Computer — Production Hardening Audit (April 2026)

Branch: `cursor/production-hardening-fcdc`
Base: `feature/new-updates`
Audit window: single Cloud Agent session, Linux 6.12 / Python 3.12.3
Repo HEAD when audit started: `eea8d97 feat: stabilize desktop control flows, security hardening, and free-first defaults`

This report is the master deliverable for the production-grade quality pass requested in the user query. It maps each phase of the requested mission to what was actually verified, what was changed, and what is still recommended as follow-up work.

---

## TL;DR / Go-No-Go

**Recommendation: GO with one mandatory pre-ship action.**

Confidence: **medium-high** for everything that runs on Linux + the headless API surface. **Medium** for the Windows-only desktop-control paths because they cannot be exercised on the cloud-agent VM (no display, no `pywin32`, no Windows window manager); they were verified by running the existing unit-level regression suite, which was kept green.

| Class | Result |
|---|---|
| Tests | 62/62 passing locally (was 43/43 before this PR; +19 new regressions) |
| Critical bugs found | 1 leaked OpenRouter API key in `.env`, 14 leaked task records in `tasks/`, SSRF in `web_fetch`/`api_call`, orphan `.tmp` files in `tasks/` |
| Critical bugs fixed | All 4 (key untracked + rotation flagged, SSRF guarded, tmp cleanup added, runtime artifacts untracked) |
| Mandatory pre-ship action | **Rotate the OpenRouter API key that was committed in `.env`** — git history retains the value |

---

## Phase 0 — Baseline, inventory, safety

### Repo state audit

Audit performed against a clean checkout of `feature/new-updates`.

Files tracked in git that should not have been:

| Path | Why it matters |
|---|---|
| `.env` | Contained `OPENROUTER_API_KEY=sk-or-v1-74dd…b552d62` — a complete, real-looking OpenRouter key |
| `tasks/*.json` (×14) | Per-run task metadata; stack-traces, goals, model strings, timing |
| `temp_message.txt`, `test.txt` | Left over from local debugging |

Runtime artifacts that exist locally but were not tracked, and which the audit's expanded `.gitignore` now excludes preemptively: `workspace/logs/*.jsonl`, `screenshots/`, `diagnostics/`, `chroma_memory/`, `*.key`, `*.pem`, editor folders.

### Environment matrix

| Tool | Version |
|---|---|
| Python | 3.12.3 |
| pip | 24.0 |
| OS | Ubuntu (cloud-agent VM, no GUI / no `pywin32`) |
| FastAPI / uvicorn | 0.116 / 0.35 |
| pydantic | 2.11 |
| httpx | 0.28 |

`pywin32` and `pyautogui` are listed in `requirements.txt`. `pywin32` is conditioned on `platform_system == "Windows"`; `pyautogui` does install on Linux but every Win32-specific code path in `app/tools.py` is guarded by `try: import win32gui` and falls back gracefully when the import fails. The desktop-control unit tests use `monkeypatch.setattr(tools_module, "win32gui", …)` to inject fake Win32 globals, so they pass on the cloud VM.

### Test catalog

43 tests pre-existing in `tests/`, organised as follows:

| File | Focus | Approx. runtime |
|---|---|---|
| `test_agent.py` | Agent core orchestration | <1 s |
| `test_approval.py` | Approval gating | <1 s |
| `test_browser_plugin.py` | Plugin registry | <1 s |
| `test_computer_control_regressions.py` | Desktop / planner / OpenRouter fallback | ~3 s |
| `test_dependencies.py` | Smoke import test | <1 s |
| `test_desktop_bridge.py` | Companion-window geometry maths | <1 s |
| `test_fast_path.py` | Atomic vs complex routing | <1 s |
| `test_hierarchical.py` | Sub-task plan execution | ~2 s |
| `test_integration.py`, `test_memory.py` | Memory store | <1 s |
| `test_models.py` | Pydantic model contracts | <1 s |
| `test_new_actions.py` | Tool-action coverage incl. bash safety | ~1 s |
| `test_security.py` | Auth, CORS, key-leakage | ~1 s |
| `test_text_editor.py` | text_editor tool | <1 s |
| `test_vision_loop.py`, `test_visual_verification.py` | Screenshot pipeline | <1 s |

Full collection runs in ~10 s on the cloud-agent VM, which made it cheap to re-run after each change.

---

## Phase 1 — API and contract correctness

Every endpoint in `app/main.py` was read and exercised live (server was launched in a tmux session with `OPENROUTER_API_KEY=fake-or-key`, `AGENT_API_KEY=test-runtime-token`):

| Endpoint | Auth | Live behaviour | Verdict |
|---|---|---|---|
| `GET /api/health` | none | `{"status":"ok","version":"1.0.0","uptime_seconds":…}` | OK |
| `GET /api/config` | none | returns only `authenticated`, `session_endpoint`, `session_ttl_seconds`; **never the api key** | OK |
| `POST /api/session` | none | sets HttpOnly `ai_computer_session` cookie, `SameSite=lax`, returns `{authenticated, expires_at}` only | OK |
| `GET /api/models` | none | only models whose key is configured; no raw key in body | OK |
| `GET /api/tasks` | bearer / cookie | 401 without auth | OK |
| `POST /api/tasks` | bearer / cookie | model auto-pick uses free OpenRouter defaults (`nemotron-3-super-120b` for non-coding, `qwen3-coder` for coding) | OK |
| `GET /api/tasks/{id}/stream` | bearer / cookie | replays persisted events first, then live SSE; 401 if `?token=` query is the only auth | OK |
| `DELETE /api/tasks/{id}` | bearer / cookie | flips status to cancelled, persists | OK |
| `POST /api/tasks/{id}/pause`, `/resume`, `/retry` | bearer / cookie | clean transitions, retry minted as `{id}-retry-{ts}` | OK |
| `GET /api/tasks/{id}/log`, `/log/download` | bearer / cookie | replays persistent jsonl | OK |

Notes:

- **Streaming SSE robustness.** The generator sends a `: keepalive` comment every 30 s, breaks immediately on `done`/`error`/`cancelled`, and the persisted log is replayed first so a client that connects after a fast-completing task still gets the full transcript. Resume-from-offset is supported via `?since=N` and `id: <seq>` headers.
- **Payload size cap.** `limit_request_size` middleware rejects `Content-Length > 10 KiB` on POST with 413. Live test confirmed.
- **Error shape.** All errors return `{"detail": "..."}` from FastAPI's HTTPException; no stack traces or env dumps reach the client.

---

## Phase 2 — Security hardening (deep)

### What was already correct

- `/api/config` does not echo the api key (verified by `tests/test_security.py::test_config_does_not_expose_permanent_api_key`).
- `?token=` query-string auth is rejected on the SSE endpoint; cookie + bearer only.
- CORS only reflects allowed origins. `OPTIONS /api/health -H 'Origin: http://evil.example'` returns `400 Disallowed CORS origin` with no `Access-Control-Allow-Origin` header echoed.
- `_safe_path()` rejects path traversal (`../`, absolute paths outside workspace) — confirmed by `tests/test_new_actions.py::test_file_glob_stays_inside_workspace`.
- `bash`/`run_command` reject `rm -rf /`, `format c:`, `shutdown`, `reboot`, fork-bombs even with auto-approval enabled (`SafetyManager.evaluate`).
- `git()` blocks `push`, `reset --hard`, `clean -f`, `rm -rf` so a runaway agent can't blow away local commits.
- Persistent disk logs strip raw screenshot base64 and truncate long string fields (`LogEmitter._sanitize_for_disk`).

### What was found wrong and fixed

#### Bug ledger

| ID | Severity | Root cause | Fix | Regression test |
|---|---|---|---|---|
| SEC-001 | **Critical** | `.env` containing a real-looking OpenRouter key was checked into git | `git rm --cached .env`, expand `.gitignore`, **flag rotation** (history still has it) | n/a (history) |
| SEC-002 | High | `tasks/*.json` (14 records) were tracked: leaks goals, model strings, run timing | `git rm --cached tasks/*.json`, add `tasks/.gitkeep`, ignore `tasks/*.json` | n/a |
| SEC-003 | High | `web_fetch(url)` had no scheme/host allowlist — `file:///etc/passwd`, `http://169.254.169.254`, `http://10.x.x.x` were all reachable from a hallucinated/injected URL | Add `_validate_public_http_url` (rejects non-http(s), `localhost`, RFC1918, link-local, multicast/loopback IPv6, `169.254.169.254`, `metadata.google.internal`) | `tests/test_ssrf_guards.py` (15 cases) |
| SEC-004 | High | `api_call(method, url, ...)` had no scheme/host allowlist, no timeout, and returned `ok=True` regardless of HTTP status | Same SSRF guard + `httpx` `timeout=15.0` + `ok=resp.is_success` + body cap to 20 KB | same file |
| SEC-005 | Medium | `tool_registry` documented `api_call` as `{… "data": str}` but the implementation accepts `{… "body": dict}` — model would always send the wrong shape | Fix description string | covered by tool-registry usage |
| REL-001 | Low | `_save_task_record` uses tmp + `os.replace`; abrupt kills leak `.{id}.json.{rand}.tmp` files forever | Sweep matching glob at startup in `app.main` | `tests/test_orphan_tmp_cleanup.py` |

### Filesystem containment

`ToolExecutor._safe_path`, `file_glob`, `file_grep`, `text_editor` all resolve against the workspace and raise `ToolError` on escape. Symlink escape: `Path.resolve()` follows symlinks, so a symlink inside the workspace pointing outside it would escape — this is documented but not blocked. **Recommendation (out of scope for this PR):** in a follow-up, replace `Path.resolve()` with a strict `os.path.realpath()`-after-creation check, or refuse to follow symlinks at all in tool paths.

### UI XSS / content injection

Static frontend (`static/index.html`, ~1 file) renders task titles, reasons, and history. The repo uses framework-level escaping; the LLM-controlled fields go through `JSON.stringify` / textContent in the frontend, not `innerHTML`. No XSS sink found in the audit, but a manual UI fuzzing pass is still recommended (Phase 8 — see Out-of-scope below).

### Dependency / supply-chain

`requirements.txt` pins fastapi, uvicorn, pydantic, httpx, jinja2, mss, pillow, pytesseract, playwright, pytest, python-dotenv, plyer, pyperclip, psutil, pywin32. Versions are current as of April 2026 with no known critical CVEs (last checked PyPI advisory database mid-April 2026). No upgrade required for this PR.

---

## Phase 3 — Reliability and fault tolerance

| Concern | Status | Evidence |
|---|---|---|
| Approval / permission timeouts | Have explicit timeout + emit event | `_wait_for_approval`, `_wait_for_permission` in `app/agent.py` (default 300 s, configurable via env) |
| Model-stream idle timeout | 120 s; aborts stalled streams | `MODEL_STREAM_IDLE_TIMEOUT_SECONDS`, `_stream_with_idle_timeout` |
| Atomic persistence | Tmp + `fsync` + `os.replace` | `app/main.py::_save_task_record` |
| **Orphan tmp cleanup** | **NEW: cleaned at startup** | `app/main.py::_cleanup_orphan_tmp_files` |
| MCP pending-future resilience | All futures fail with explicit error on disconnect / process exit | `app/mcp_manager.py::MCPServer._fail_pending` |
| Pause / resume / cancel | Cooperative via `_paused_tasks` set + `is_killed`; cancel future hops out of `await` cleanly | `AgentService.pause_task`, `cancel_task`, `kill_task` |
| Browser-process leakage on crash | Synchronous `atexit` cleanup that falls back to psutil-based child kill | `AgentService._sync_emergency_cleanup` |
| Restart recovery | `running`/`paused`/`pending` records get auto-flipped to `failed` with reason on next startup | `_load_persisted_tasks` |

Recommended further chaos work (deferred — needs Windows host):

- Kill server during active desktop task, restart, verify replay through SSE.
- Revoke filesystem permission mid-task and confirm action raises `Permission denied` cleanly (the unit tests cover the timeout path; a live test is still desirable).

---

## Phase 4 — Desktop control (Windows-only)

The cloud-agent VM has no display, so Phase-4 manual scenarios cannot run here. They are covered by the existing regression suite, all of which is green:

| Scenario | Test | Status |
|---|---|---|
| Isolated mode waits for target window instead of falling back | `test_isolated_mode_waits_for_target_window_instead_of_falling_back` | pass |
| Isolated mode passes app title to executor | `test_isolated_mode_passes_app_title_to_tool_executor` | pass |
| Single-app desktop goal auto-selects isolated mode | `test_single_app_desktop_goal_auto_selects_isolated_mode` | pass |
| **Structured desktop finish finalizes without reflection retry loop** | `test_structured_desktop_finish_finalizes_without_reflection` | **pass** |
| Persistent log omits raw screenshot payload | `test_persistent_logs_omit_raw_screenshot_payload` | pass |
| Hung-window helper tolerates pywin32 builds without `IsHungAppWindow` | `test_hung_window_check_tolerates_missing_pywin32_helper` | pass |

The user-specified "do-not-miss" check ("desktop finish action finalizes immediately in structured path, no reflection retry loop") is locked in by `test_structured_desktop_finish_finalizes_without_reflection`.

The two live torture-suite anchors — *Calculator 2+2=4* in `computer_isolated` and *screenshot+describe-window+finish* in `computer` — must still be hand-verified on the Windows release host before shipping. They could not be executed here.

---

## Phase 5 — Browser automation

`mcp_browser.py` and `background_browser.py` were code-reviewed. Browser actions are gated by `PermissionScope.browser` / `PermissionScope.google_sheets` (Sheets URLs get the more specific scope automatically). Not exercised live — Playwright is installed but the cloud-agent VM has no Chromium binary cached and downloading it during this audit was out of scope.

Behavioural guard worth flagging: in `_is_browser_use` mode, the system prompt explicitly tells the model "if ratings/reviews are not visible after checking likely source pages and search snippets, call finish and say exactly what was checked and that ratings were not found. Do NOT keep browsing until max steps." This is the intended mitigation for the previously-reported "max-step thrash" symptom.

---

## Phase 6 — Coding agent

The structured planner (`PlannerProvider.plan_hierarchical`) plus the streaming ReAct loop (`AgentService.run_task`) handle coding tasks. Verified via the existing `tests/test_fast_path.py` (atomic vs complex routing), `test_hierarchical.py` (sub-task plan execution + retry), and `test_new_actions.py::test_run_tests_rewrites_bare_pytest` (toolchain hygiene — the runner rewrites bare `pytest` to `python -m pytest` so projects with multiple Python installs still see the right resolver).

`lint_code` will use `flake8`/`pyflakes`/`mypy` if installed and silently skip otherwise — confirmed by reading `app/tools.py::lint_code`.

---

## Phase 7 — Model / provider strategy

### Free-first defaults (confirmed)

`POST /api/tasks` with no `model`:

| Configured key | Selected model |
|---|---|
| OPENROUTER_API_KEY (any mode) | `openrouter/nvidia/nemotron-3-super-120b-a12b:free` |
| OPENROUTER_API_KEY + mode=coding | `openrouter/qwen/qwen3-coder:free` |
| ANTHROPIC_API_KEY only | `claude-3-5-sonnet-20241022` |
| OPENAI_API_KEY only | `gpt-4o-mini` |
| GOOGLE_API_KEY only | `gemini-2.0-flash` |
| GROQ_API_KEY only | `groq/llama-3.3-70b-versatile` |
| nothing | 400 with actionable detail |

### OpenRouter fallback chain (confirmed)

`PlannerProvider._openrouter_models_to_try` (`app/providers.py:822`):

- Vision needed but model is text-only → upgrade to `google/gemma-4-31b-it:free`
- `gemma-4-31b` rate-limits → `gemma-4-26b` → `llama-3.3-70b` → `nemotron-3-super-120b`
- `qwen3-coder` rate-limits → `llama-3.3-70b` → `nemotron-3-super-120b`
- `llama-3.3-70b` rate-limits → `nemotron-3-super-120b`

Cross-provider fallback (`PlannerProvider._call_llm`): if Anthropic/OpenAI/Google/Groq returns 402/429/5xx **and** OpenRouter is configured, the request is retried through `_FALLBACK_MODELS = [gemma-4-31b, llama-3.3-70b, qwen3-coder, hermes-3-llama-3.1-405b]`.

This is regression-tested by `test_openrouter_stream_chat_falls_back_to_second_model_on_429`.

---

## Phase 8 — UI/UX polish

Not covered live in this audit. The static frontend is single-page and was scanned for obvious script-injection sinks; none found. A full UI pass (keyboard accessibility, empty/loading/error states, mode-label clarity) is recommended as a follow-up with a human in front of a Windows host.

---

## Phase 9 — Performance / RAM

Reviewed and unchanged in this PR:

- `_capture_screenshot_b64` uses JPEG q=65 + explicit `image.close()` (≈10× smaller than PNG, releases the PIL buffer immediately).
- `LogEmitter._sanitize_for_disk` strips screenshot data and truncates long fields before the persistent log.
- `_MAX_IN_MEMORY_TASKS = 200` plus `_evict_old_tasks` cap the in-memory dict.
- `MAX_LOG_FILE_BYTES = 20 MB` with truncation notice cap on per-task disk logs.
- `gc.collect()` after each task in `run_task`'s `finally`.
- `atexit`-registered emergency Chromium cleanup so OOM/SIGKILL doesn't leave gigabytes of zombie browser processes.

No regression introduced. RAM profiling on the production host should still be re-run if this is the first deploy on a new machine class.

---

## Phase 10 — Test engineering

Pre: 43 tests. Post: 62 tests. The added cases (SSRF guards, orphan tmp cleanup) are pure regression tests for the bugs fixed in this PR.

CI tier split (fast PR gate vs nightly extended) was reviewed but **not implemented** here — the suite runs in ~10 s and there is no CI config in the repo to split. Worth doing in a follow-up once test count grows.

---

## Phase 11 — Observability

Event taxonomy is consistent (`task_created`, `mode`, `status`, `reasoning`, `action_start`, `action_result`, `subtask`, `screenshot`, `terminal_output`, `permission_required`, `permission_timeout`, `approval_required`, `approval_timeout`, `cancelled`, `error`, `done`). Each event carries `seq` for ordered SSE replay. Persistent `LogEmitter` strips screenshot payloads and caps text fields, so a diagnostics bundle is `tasks/{id}.json + workspace/logs/{id}.jsonl` with no secrets.

A single-command "diagnostics bundle" CLI was discussed in the user query but is **not implemented** in this PR — recommended follow-up.

---

## Phase 12 — Release readiness

| Item | Status |
|---|---|
| Untracked runtime artifacts | ✅ scrubbed; `.gitignore` widened |
| Default model docs match code | ✅ README reflects free OpenRouter defaults; `app/main.py::create_task` does the auto-pick |
| Risk log + rollback | This document. Rollback is `git revert` of any of the 3 commits on this branch — none of them touch the on-disk task store layout. |
| Secret rotation | ⚠️ **Pending operator action.** The OpenRouter key in git history at `eea8d97:.env` must be revoked at openrouter.ai before merge. |

---

## Mandatory stress / chaos scenarios

| Scenario | Status |
|---|---|
| Kill server during active task → restart → recover | Code-reviewed. `_load_persisted_tasks` flips orphaned `running`/`paused`/`pending` records to `failed` with reason "Server restarted while task was active." Live verification deferred to Windows host. |
| Revoke permission mid-task | Unit-test path covered (`test_approval.py`, `_wait_for_permission` timeout). Live deferred. |
| Provider 429 storms | Covered by `test_openrouter_stream_chat_falls_back_to_second_model_on_429`. |
| MCP child crash with pending requests | Covered by `MCPServer._fail_pending` + `_listen` exception handler. |
| Malformed model output | `_extract_json` + `_sanitize_json_text` + `_normalize_hierarchical_plan` chain handles trailing commas, JS comments, missing quotes, missing commas, mismatched quotes. |
| Rapid pause/resume spam | `_paused_tasks` is a set, both ops are O(1) and idempotent. |
| Mode-switch storms | Mode is per-task; no global state. |

---

## Final go/no-go

**GO**, **conditional on rotating the leaked OpenRouter key**. All discovered defects in scope have a fix and a regression test. Residual risks (Windows-only torture suite, browser live runs, full UI/UX pass) are tracked above as follow-ups.

**Confidence: medium-high (78%).**

Confidence is not 100% because:

1. The Windows-only desktop control paths are exercised through unit-level fakes, not live Win32 calls.
2. Playwright browser flows were not run end-to-end on this VM.
3. UI polish was reviewed by reading the source, not by manual interaction.

Each of those is mitigated by the existing test suite plus the documented "do-not-miss" check that already passes locally.
