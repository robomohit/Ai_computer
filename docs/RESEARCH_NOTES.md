# Research Notes (OpenClaw Discovery)

OpenClaw appends dated research notes here each night (3 AM cron).
Claude reads this during its 9 AM survey step before picking work from the queue.

Sources should be cited inline (URLs). Each daily section has its own heading.

---

## 2026-05-01 (scan: codebase patterns)

- **Memory search return-type inconsistency** — `memory.search()` returns plain strings in some contexts but `MemoryItem` objects with `.content` in others. Tests like `test_delegate_parser` (fixed in IDEA-06), `test_hierarchical_success`, and others fail with `AttributeError: 'str' object has no attribute 'content'`. Pattern: code checks `m.content` without defensive `getattr(m, 'content', m)` guard. Source: `tests/test_hierarchical.py:23`, `tests/test_agent.py::test_delegate_parser` [file:app/agent.py:629].
- **LogEmitter async race condition** — `emit()` submits disk writes to single-worker `ThreadPoolExecutor`, but `read_log()` can be called before writes complete. Pattern is fixed in `LogEmitter.flush()` (IDEA-07) but test `test_log_emitter_seek_replay_uses_binary_offsets_for_utf8` still fails with empty replay — likely needs `emitter.flush()` call before `read_log()` in test. Source: `tests/test_project_folder_runtime.py:102`, `app/log_emitter.py:165`.
- **Auth 401 failures in security tests** — three tests (`test_permanent_api_key_still_authenticates_server_api`, `test_task_id_rejects_path_traversal`, `test_create_task_internal_error_does_not_leak_details`) return 401 instead of expected codes. Pattern: `_client()` fixture sets `AGENT_API_KEY=token123` but server may not pick it up correctly; `main.py` generates random key if env var unset and no persisted key file exists. The auth check may be comparing against a different key. Source: `tests/test_security.py:33,60,76`, `app/main.py:21`.
- **Fast-path routing assertion failures** — `test_atomic_fast_path_routing` and `test_complex_task_routing` show `call_llm_called` stays False. Pattern: `PlannerProvider._call_llm` patching at `app.providers` module level may not match actual call site due to import/module aliasing (relative imports vs absolute). Source: `tests/test_fast_path.py:49,88`, `app/providers.py`.
- **JPEG magic-byte / vision-loop failures** — `test_vision_loop.py:28` and `test_visual_verification.py:20` expect base64-decoded payload to start with JPEG magic bytes (`\xff\xd8\xff`). Pattern: screenshot encoder may produce PNG bytes, or mock fixture provides wrong format. Source: `tests/test_vision_loop.py:28`, `tests/test_visual_verification.py:20`.
- **Hierarchical memory `.content` access** — same family as first bullet: `tests/test_hierarchical.py` checks `m.content` on memory search results which may be strings under test mocking. Needs defensive getter pattern used in `agent.py:629/633`. Source: `tests/test_hierarchical.py:23,44,70`.
- **TextEditorTool undo stores full copy pre-edit** — `str_replace`/`insert` store entire file text in `self._history` before modification. Pattern: fine for small files but unbounded growth on large files across many edits (no limit). Source: `app/text_editor.py:49,67`.
- **Missing `LogEmitter.flush()` usage** — test `test_log_emitter_seek_replay_uses_binary_offsets_for_utf8` fails because background thread writes may not be visible to `read_log()` called immediately after `emit()`. Pattern: needs explicit `flush()` before read assertions. Source: `tests/test_project_folder_runtime.py:102`, `app/log_emitter.py:217`.

---

## 2026-05-03 (scan: triage)

**Queue health overview:**
- Total IDEAs: 32 (includes 10 UI Phases A–F)
- Status breakdown: ~18 queued, ~11 done, ~3 split/blocked
- Done in last 72h: IDEA-08a through 08f (12 pre-existing test failures), IDEA-09 (vendored mermaid), IDEA-03 (/healthz endpoint)

**Critical path observations:**
- **UI redesign is a critical bottleneck.** Phases A, D, B, C1, E, F, C2 form a linear dependency chain (7 IDEAs, ~500 LOC total scope). Phase A (sidebar restructure) must ship first to unblock B/D. Currently queued with no in-progress marker.
- **Quick wins available:** IDEA-02 (Copy-task button, ~25 LOC), IDEA-05 (Auto-pause on loops, ~20 LOC), IDEA-04 (Duration badge, ~30 LOC) are independent and low-risk. Could batch these to unblock queue attention for Phase A start.
- **Dependency clarity:** Phase B explicitly notes "depends on Phase D — IDEA-08 — having shipped first" (line 257), but Phase D is purely removal (drop READY pill). D's 25 LOC should ship *before* B to avoid topbar slot conflict. Current queue order (D at line 248, B at line 250) is correct but not marked as dependency.

**Risk flags:**
- **localStorage mode persistence (IDEA-01):** Low-risk but untested. No Playwright smoke test currently specified; suggest adding one.
- **TextEditorTool memory cap (IDEA-2026-05-01-01):** "~10–15 LOC" scope estimate may be low if history format is complex. Worth a 15min code read before picking.
- **Phase F refactor (split HTML/CSS/JS):** Highest-risk in batch (5000 LOC moved). Recommend running Playwright full suite before claiming "zero visual change."

**Blocker status:**
- None currently. All queued items are unblocked or have explicit (but unmarked) soft dependencies.

**Recommendations for next PM run:**
1. Pick Phase D (IDEA-08) first — it's a pure delete, ~5 min, unblocks Phase B topbar work.
2. Batch quick-wins (IDEA-02, 04, 05) in one PR to reduce queue size.
3. Start Phase A (IDEA-07) after quick-wins; mark as in-progress to signal focus.
4. Add Playwright smoke tests to localStorage IDEA-01 acceptance criteria before work starts.

---

## 2026-05-04 (scan: triage)

**Queue shape snapshot:**
- 32 total IDEAs: ~18 queued, 11 done, 1 needs_human (IDEA-10), 2 split/blocked
- Velocity: 3 shipped past 24h (Phase D, TextEditor cap, /api/mcp cache)
- Test suite: 91 passed, 1 skipped, 0 failed (3-test net gain from recent work)

**Dependency resolution — UI Phases unblocked:**
- Phase D (IDEA-08: drop READY pill) ✅ shipped 2026-05-03
- Phase B (IDEA-09: topbar breadcrumb) now unblocked — was waiting for Phase D topbar slot to free
- Phases A→F form a sequential chain; no new blockers detected. A (sidebar restructure) is queued and can start immediately
- Source: `docs/FEATURE_IDEAS_QUEUE.md:257` (Phase B dependency note), confirmed resolved by PM notes from 2026-05-03

**Quick-win batch candidate:**
- IDEA-02 (Copy-task button, ~25 LOC) + IDEA-04 (Duration badge, ~30 LOC) + IDEA-05 (Auto-pause loops, ~20 LOC) = ~75 LOC, zero interdependencies
- All three are feature-complete, have clear acceptance criteria, low test complexity
- Recommendation: batch into single PR to unblock queue attention for Phase A (sidebar) which is higher-risk (~200 LOC)

**Blocking issue — no progress possible:**
- IDEA-2026-04-30-10 (Persist API key) marked needs_human: implementation wants `workspace/.api_key` but `workspace/` is never-touch. Hard blocker until human selects alternate path (e.g., `~/.agent_key` or `$HOME/.config/ai_computer/.api_key`) or confirms rotating keys are acceptable behavior
- No other queued IDEAs depend on this, so queue progression unaffected

**New encoding risk detected:**
- IDEA-2026-05-03-01: `app/text_editor.py:88` — `undo_edit()` calls `p.write_text(old)` with no encoding, uses platform default (cp1252 on Windows). Silent UTF-8 corruption on undo for any non-ASCII file
- 1-LOC fix: add `encoding="utf-8"` to write_text call. Marked queued but suggest picking after quick-wins to avoid context thrash

**No stale findings.**
- All queued IDEAs < 5 days old, queue has no drift (timestamps align with recent PM work)
- Test failures from 2026-05-01 are fully resolved (IDEA-08a through 08f done)

### Implications for Ai_computer

- **Critical path:** UI overhaul (Phases A–F) is now fully unblocked at Phase A; no surprises in the dependency chain. Recommend committing PM to Phase A next cycle to signal that the UI overhaul is underway and sustained focus. Current queue positioning (queued but not in_progress) makes it easy to starve for other work.
- **Short-term momentum:** Quick-wins batch (02, 04, 05) would reduce queue backlog and signal progress. Pairs well with Phase A starting — quick wins complete in ~30 min, clearing mental space for the 200+ LOC sidebar refactor.
- **Encoding regression:** The UTF-8 undo bug is platform-specific (Windows only); suggest testing on Windows after merging to prevent undetected corruption in customer workflows. Mark IDEA-2026-05-03-01 as "test on Windows" in acceptance criteria.

## 2026-05-05 — Codebase patterns

Scanned two random `app/*.py` files end-to-end: `app/providers.py` (1444 lines) and `app/tool_registry.py` (144 lines).

- **Multi-provider fallback chain** (providers.py:689–1035): Primary provider selected by model string. On rate-limit (402, 429, 5xx), cascades to hardcoded OpenRouter free models (gemma-4-31b-it, llama-3.3-70b, nemotron) with exponential backoff (2^attempt seconds), 3 retries per model. Fallback list is static; no alerting if all models sunset.
- **Aggressive JSON repair pipeline** (providers.py:483–527): Direct parse → sanitized parse (strip //, fix trailing commas, quote bare keys) → aggressive repair (escape newlines) → final fallback. Handles common LLM malformations (JS-style comments, missing commas).
- **Mode-specific system prompts** (providers.py:20–144): Coding (no screenshots, filesystem-first rules), computer_use (DOM-based, no pixel coords), default (hierarchical with screenshots). Rules hardcoded per mode; consistent structure but duplicated instructions across modes.
- **Streaming tool call assembly** (providers.py:1155–1320): Accumulates thought buffer and tool JSON across SSE chunks. Detects finish_reason to mark completion. **Assumes single tool_call per response** (line 1297 returns immediately); if OpenRouter emits parallel tool_calls, only first is captured.
- **Win32-specific screenshot capture** (providers.py:373–461): PrintWindow + device contexts. Explicit buffer cleanup (`.copy()` breaks PIL references). Thumbnail to 1280×800, JPEG quality=75. No Linux/macOS equivalent paths.
- **Modular tool packs** (tool_registry.py:60–70): Core (finish, request_permission, memory_recall, todo_write) + mode-specific subsets (filesystem, terminal, browser, computer, web). Deduplication in `get_tool_guidance()` prevents redundant tool visibility.
- **Regex-fragile schema generation** (tool_registry.py:84–122): `_json_schema_from_description()` infers types from description text via regex. Type matching is case-sensitive ("int", "dict", "list" must be lowercase; "Dict" or "List" missed). Current descriptions use lowercase, but no enforcement.

### Implications for Ai_computer

- **JSON return type fragility**: `_extract_json` returns `Any`. Most callers assume dict, but if LLM returns top-level array or plain string, agent crashes. Robust JSON repair, but not type-agnostic. Low immediate risk (LLMs trained for objects), but brittle on outliers.
- **Parallel tool call loss**: `stream_chat_with_tools` returns after first tool_call (line 1297). OpenRouter can emit multiple tool_calls in one SSE chunk (rare). Only first is captured; others lost silently.
- **Key validation deferred to first API call**: Provider keys loaded at `__init__` but never checked for emptiness or syntax. 401/403 errors delay feedback. Invalid key detected only on first task, not on startup.
- **Hardcoded fallback model list without alerts**: If OpenRouter sunsetts gemma-4-31b-it or llama-3.3-70b, the fallback chain silently steps down. No mechanism to alert on full fallback exhaustion or model deprecation.

## 2026-05-06 (scan: tech radar — FastAPI/SSE/asyncio patterns)

- **FastAPI lifespan async initialization** — `_lifespan` context manager at `app/main.py:32` fires three background tasks on startup (`_init_mcp`, `start_telegram`, `start_discord`) using `asyncio.create_task()` without awaiting. Pattern: fire-and-forget design; lifespan yields before tasks complete. Implication: `MCP_MANAGER` may not be ready on first client requests (mitigated by `/api/mcp` returning `{initializing: true}` at line 472, but startup race window exists). Source: `app/main.py:32–56`.
- **SSE event generator with client-disconnect polling** — `stream_task` endpoint (line 870) uses `await request.is_disconnected()` inside an infinite loop with 30s asyncio.wait_for timeout. Pattern: yields keepalive heartbeats (`: keepalive\n\n`) on timeout. Advantage: responsive to client close. Limitation: 30s timeout may miss slow clients; hardcoded ping interval not tunable. Source: `app/main.py:870–914`.
- **Async queue-based event subscription** — `log_emitter.subscribe(task_id)` returns an asyncio.Queue; SSE handler pops messages with `await q.get()`. Pattern decouples event emission from streaming transport (allows multiple concurrent subscribers). Efficient but unbounded queue growth if subscriber lags. Source: `app/main.py:896`, `app/log_emitter.py` (subscription registry not reviewed but pattern clear from usage).
- **Task lifecycle management via asyncio.Task dict** — `_active_tasks: dict[str, asyncio.Task]` at `app/agent.py:338` stores per-task async workers. Kill/pause control via `task.cancel()` (line 369) and `asyncio.Event` signaling (pause polling at line 858–859). Pattern is sound; cancellation exception handling not reviewed but cleanup via `finally` block likely present. Source: `app/agent.py:338–374`.
- **Sync-to-async bridge via asyncio.to_thread** — Memory operations (search, add_action_result) called from async context using `await asyncio.to_thread(...)` at `app/agent.py:201`. Pattern prevents blocking the event loop on synchronous I/O. Limitation: requires Py3.9+; thread pool overhead for short operations (memory.add is likely <10ms). Source: `app/agent.py:201`.
- **Healthz caching with mutable dict state** — `_healthz_cache: dict = {"ts": 0.0, "result": None}` at `app/main.py:448` is manually updated in the handler (lines 453–461). Pattern is simple but not thread-safe (if multiple concurrent GETs arrive during cache update, reads may see partial state). Practical issue: very low since health check is fast and cache TTL is 30s. Modern approach would use `@lru_cache` or a dedicated cache lib. Source: `app/main.py:448–462`.
- **Mode-specific system prompts hardcoded per provider** — Coding mode (providers.py line 49), computer_use mode (implied), hierarchical (line 22) each have full system prompt templates. Duplication across modes (~30% repeat instructions). No fallback or inheritance pattern. Maintenance risk: rules updates require touching all three. Source: `app/providers.py:20–144`.

### Implications for Ai_computer

- **Startup race windows**: Fire-and-forget MCP init (create_task without await) means early client requests might hit `initializing:true`. Not a blocker (UI retries), but adds latency to first access. Consider replacing `asyncio.create_task(_init_mcp)` with an awaited gather or deferring MCP init to lazy first-use.
- **Event queue unbounded growth risk**: Slow SSE clients (or malicious long-poll attackers) can accumulate unread events in the queue forever. Not currently observed (likely due to client-side disconnect), but a production hardening issue. Add a high-water mark warning if queue depth exceeds N items.
- **Healthz cache thread-unsafety is theoretical**: 30s TTL and fast health check mean practical risk is negligible. Document as low-priority cleanup (use a proper cache lib if general caching infrastructure is needed elsewhere).
- **System prompt duplication maintenance burden**: Current approach is acceptable at ~400 lines total, but future mode expansions will require copy-paste. Consider a dict-based prompt builder with shared instruction blocks (e.g., `{"common": "...", "coding": {...}, "computer": {...}}`).

## 2026-05-08 — Competitor watch (Aider, OpenHands, Cursor, Open-Interpreter, Continue.dev, Devin)

- **Aider adds thinking-token budgets** — `/think-tokens` command (supports human-readable formats: 8k, 10.5k, 0.5M) and `/reasoning-effort` control for model reasoning level. Pattern: user-visible knobs to tune model introspection depth and cost. Source: [github.com/Aider-AI/aider/releases](https://github.com/Aider-AI/aider/releases); Aider self-wrote 92% of this release.
- **OpenHands ships Enterprise Control Plane** (May 6) — "Agent Control Plane" for running agents across orgs; Task List tab in UI showing real-time agent task breakdown with status updates; slash command menu in chat showing available agent skills. Pattern: enterprise-grade ops visibility + UX polish for agent task tracking. Source: [openhands.org/updates](https://www.openhands.org/updates/).
- **Cursor 3.0 (April 2) launches Agents Window + Security Reviewer** — Dedicated Agents Window runs multiple agents in parallel across repos/worktrees/cloud/SSH. Security Reviewer (May beta on Teams/Enterprise) is always-on, checks every PR for vulnerabilities, auth regressions, privacy/data-handling risks, tool auto-approvals, and prompt-injection attacks. Interactive canvases render dashboards/diffs/to-do lists as durable artifacts. Source: [cursor.com/changelog](https://cursor.com/changelog).
- **Open-Interpreter adds `--os` feature (Anthropic-powered computer use)** — New computer tools with screenpipe demo; remote Ollama support; dynamic tool discovery. Pattern: native computer-use integration mirrors Claude's built-in capabilities. Source: [github.com/OpenInterpreter/open-interpreter/releases](https://github.com/OpenInterpreter/open-interpreter/releases).
- **Continue.dev Agent Mode now uses AST-based targeted edits** — Multi-step task planning; avoids full-file rewrites by applying edits via AST; `--id` option connects to existing remote agents via tunnel. Pattern: precision-edit strategy for reliability in large files. Source: [changelog.continue.dev](https://changelog.continue.dev/).
- **Devin 2.2 (Feb 2026) adds desktop app testing + self-verify loop** — Can launch and test desktop applications on its own Linux desktop; runs tests, auto-fixes code, sends back screen recordings. Parallel sessions; streaming thoughts; Fast Mode (~2x speed, 4x ACU cost). Source: [cognition.ai/blog/introducing-devin-2-2](https://cognition.ai/blog/introducing-devin-2-2).

### Implications for Ai_computer

- **Security scanning as differentiator**: Cursor's Security Reviewer runs PR checks autonomously (vulnerabilities, auth, privacy, injection). AI_computer has no built-in security scanning layer. Adding a `--security-scan` mode that checks code changes against OWASP rules before shipping could be a high-impact feature (pairs well with existing desktop app testing capability from Devin comparison).
- **Task List UI missing**: OpenHands exposes agent task breakdown in real-time (Task List tab). AI_computer tracks task history but not live task queue visibility. A "Current Tasks" panel in the UI showing what the agent is working on (from `_active_tasks` dict in agent.py:338) could improve UX and match competitor parity.
- **Thinking/reasoning budgets unexposed**: Aider exposes thinking token control and reasoning-effort knobs. AI_computer uses Claude Haiku by default but has no user-facing way to adjust reasoning depth or thinking budget. Exposing these as query params (e.g., `?thinking_budget=10k&reasoning_effort=high`) could unlock advanced use cases without code changes.
- **Parallel agent execution**: Cursor (Agents Window) and Devin (parallel sessions) both support multiple agents in parallel. AI_computer is single-task serial. No blocker for multi-agent scenarios (SSE can multiplex), but feature parity would require UI/UX redesign.

## 2026-05-10 — Tech radar (FastAPI/SSE/asyncio patterns, LLM provider features)

- **Two-tier HTTP client strategy** — Persistent non-streaming httpx.Client (timeout=300s, line 705) vs ephemeral AsyncClient for streaming with custom timeouts (connect=15.0, read=90.0, write=30.0, pool=10.0, lines 1127-1128). Pattern decouples timeout strategy: long reads for streaming, short connect for fire-and-forget. Trade-off: ephemeral client loses TCP connection pooling benefit; reuses SSL handshake cost per stream. Source: `app/providers.py:705`, lines 1127-1128, 933, 969 (sync fallback clients also use timeout=300).
- **Parallel tool call accumulation (IDEA-2026-05-05-01 merged)** — `stream_chat_with_tools()` method (lines 1158-1327) now properly collects ALL tool calls per index into `tool_calls_accum` dict (lines 1271-1283), emitting in order on finish_reason (lines 1285-1304). Fixes prior silent loss of parallel calls. Pattern: maintains separate entry per index with id/name/args_buffer; merges on finish. Robust but increases memory footprint for long-streaming responses. Source: `app/providers.py:1158-1327`.
- **Vision model detection via string matching** — Simple heuristic checks for keywords ["vision", "vl", "gemini", "claude", "gpt-4o", "gpt-4-turbo", "pixtral", "llava", "gemma"] in model name (lines 818-820, 1074-1076, 1196-1198). Pattern: no provider-specific API calls or capability introspection. Fragility: new vision models (e.g., "claude-4-vision") may be missed; older models (e.g., Gemini Nano) misidentified. Upgrade: use provider-specific capability APIs (e.g., OpenAI model.capabilities, Anthropic model card). Source: `app/providers.py:818-820, 1074-1076, 1196-1198`.
- **Claude 3.7 Sonnet available but not primary choice** — Model list includes `claude-3-7-sonnet-20250219` (line 585) but auto-selector defaults to `claude-3-5-sonnet-20241022` (line 685). 3.7 is newer (Feb 2025) and may offer better reasoning/caching, but is lower-priority than OpenRouter free models. Pattern: explicit model selection takes precedence; auto-picker is conservative. Implication: advanced features (thinking tokens, extended context) are opt-in only. Source: `app/main.py:574-690`.
- **Rate-limit fallback chain (OpenRouter models_to_try)** — `_openrouter_models_to_try()` (lines 872-910) returns ordered model list with Gemma-31B → Gemma-26B → Llama-70B → Nemotron fallback. Caller (`_chat_openrouter`, lines 817-870) silently retries next model on 402/429. Pattern: opaque failover; no logging until line 843 for HTTP errors. Trade-off: users don't know which fallback model served their request (important for reproducibility and cost tracking). Source: `app/providers.py:872-910, 817-870`.
- **SSE keepalive timeout is hardcoded at 30s** — `stream_task` endpoint (line 902) awaits `q.get()` with fixed `asyncio.wait_for(..., timeout=30.0)`. Pattern: yields colon-keepalive on timeout to prevent client-side connection close. Limitation: not tunable per client/request; slow networks (e.g., metered mobile) may experience mid-stream timeout if no events arrive in 30s. Source: `app/main.py:870-914`.

### Implications for Ai_computer

- **TCP connection pooling vs streaming latency**: The per-stream AsyncClient creation (line 1127) may incur unnecessary SSL handshake cost on each stream. Consider whether keeping a single persistent AsyncClient with streaming-specific timeouts would reduce overhead without sacrificing per-request isolation. Benchmark: compare 1-stream vs 10-stream throughput with persistent vs ephemeral clients.
- **Vision model detection needs provider introspection**: Current string matching will fail for future models (e.g., "Claude-4-Vision-Oct-2026"). Recommend adding a provider capability check at initialization: OpenAI `get_model()` API, Google `Model.get()`, OpenRouter model card JSON. Tier 2: Implement `is_vision_capable(model_name, provider)` utility that consults a small cache/JSON file for known models.
- **Claude 3.7 Sonnet features (thinking, extended cache) are hidden**: If thinking tokens or improved caching in 3.7+ could improve task success rate or reduce token spend, surface them via CLI flags or a "reasoning_level" param (similar to Aider's `/reasoning-effort`). Pairs well with IDEA-2026-05-08-01 (active task API).
- **Fallback model choice is silent and non-deterministic**: Users running the same prompt twice may get different models (if first model rate-limits). No audit trail. Recommend logging fallback events at INFO level (not just errors) and exposing final model via `/api/task/{task_id}` response header or SSE event (e.g., `{"type": "provider_info", "model": "...", "fallback": true}`).
- **SSE keepalive timeout should be configurable**: The 30s hardcode is safe for fast networks but risky on mobile. Suggest adding a `?keepalive_timeout_seconds=60` query param to `/api/tasks/{task_id}/stream` (default 30), with server-side validation (min 5s, max 300s) to prevent abuse.

## 2026-05-13 — Codebase patterns

Scanned two random `app/*.py` files end-to-end: `app/memory.py` (704 lines) and `app/mcp_manager.py` (404 lines).

- **Graceful degradation fallback in MemoryStore** — If ChromaDB fails to import or init, falls back to `_FallbackCollection` pure keyword matching (lines 17–78). Fallback implements same interface (add/query/get/delete/update) so callers don't know the diff. Pattern: safe, but dual code paths introduce maintenance risk if Chroma and fallback diverge (e.g., metadata schema changes). Source: `app/memory.py:17-310`.
- **Hybrid retrieval scoring (6-factor)** — `recall_sessions()` combines: cosine (0.6 weight) + BM25 (0.4 weight) + temporal decay (half-life 30 days, exponential) + reinforcement boost (log-scaled by recall_count) + MMR re-rank (Jaccard-based) + normalization. All factors tunable (magic numbers: k1=1.5, b=0.75 in BM25; lam=0.7 in MMR) but not externalized. Source: `app/memory.py:157-225, 395-422`.
- **Consolidation deduplication O(n²)** — `consolidate()` clusters near-duplicate summaries by Jaccard ≥0.88 threshold, merges into canonical + task_id list. No parallelization; runs synchronously (blocks agent loop). At 1000 summaries, ~1M Jaccard comparisons. Auto-trigger every 50 new summaries (line 269) means long tasks may trigger mid-run. Source: `app/memory.py:466-571`.
- **Per-task sliding window with lazy enforcement** — `enforce_sliding_window()` bounds task's memory by archiving oldest half as summary if total > MAX_TEXT_FIELD_CHARS. Only triggers on `add_action_result()` (line 622), not on a schedule. Stale action_result items persist in memory until next action fires. Source: `app/memory.py:677-703`.
- **JSON-RPC subprocess bridge with request-ID round-trip matching** — `MCPServer` wraps spawned subprocess, listener reads line-delimited JSON, matches responses to pending futures by ID in `_pending[req_id]` dict. Listener crash (exception, not CancelledError) logs and silently exits; server stays `running` status but is dead, future `call()` times out after 60s before detecting. Source: `app/mcp_manager.py:19-212, 117-151`.
- **Configurable MCP server definitions with variable expansion** — `_load_dynamic_specs()` loads from `AI_COMPUTER_MCP_CONFIG` env var or `workspace/mcp_servers.{json,local.json}`. Supports `${workspace}`, `${home}` expansion in cmd/env (simple string replace, no escape syntax — paths containing literal `${workspace}` will corrupt). Multi-config merge: later dicts override earlier (no warning if server name collides). Source: `app/mcp_manager.py:251-318`.
- **Idempotent MCP re-initialization with parallel startup** — `initialize_default_servers()` diffs desired vs current, stops stale, restarts changed, starts new. Parallel startup via `asyncio.gather(..., return_exceptions=True)` so one failure doesn't block others. Listener task cancellation uses `asyncio.shield` (line 100) — pattern correct but unconventional. Source: `app/mcp_manager.py:320-370, 96-115`.
- **Windows npx.cmd compatibility** — Rewrites `npx` to `npx.cmd` on Windows (line 45–46) for PATH resolution. Pattern specific to npm tooling. Source: `app/mcp_manager.py:44-46`.

### Implications for Ai_computer

- **Consolidation latency spike risk**: O(n²) Jaccard at 50-summary auto-trigger means a 500-summary store runs 125k comparisons synchronously when the 500th summary is written. If consolidation runs mid-task, agent loop hangs for seconds. Recommend: (a) run consolidation async in background, or (b) reduce AUTO_CONSOLIDATE_EVERY to 20 to keep spikes small, or (c) parallelize Jaccard via multiprocessing.
- **Listener death is silent**: If `_listen()` encounters an exception in JSON parsing or other I/O (lines 117–151), it logs and exits, but `MCPServer.status` stays `"running"`. Subsequent `call()` requests will timeout after 60s before detecting the dead listener. Recommend: add a watchdog timer to detect listener silence, or proactively set `status = "dead"` in the exception handler (line 148).
- **Config variable expansion can corrupt paths**: Simple string replace means `${workspace}` is not escapable. A user with a path like `/home/user/${workspace}/project` will end up with `/home/user/<actual_workspace>/project` silently. Recommend: switch to `string.Template` or stricter parsing that validates the token is surrounded by word boundaries or delimiters.
- **Dual memory code paths (Chroma vs Fallback) need parity testing**: If Chroma is disabled (USE_CHROMA=0) for offline testing, the fallback's token-based query will diverge from production Chroma behavior. Recommend: add a parity test (`test_memory_chroma_vs_fallback_consistency.py`) that runs the same recall sequence on both backends and asserts matching results (within rank tolerance).

## 2026-05-15 — Competitor watch (Aider, OpenHands, Cursor, Open-Interpreter, Continue.dev, Devin)

- **Aider model ecosystem expansion** — Now supports `openrouter/google/gemma-3-27b-it`, Grok-4 (`xai/grok-4`, `openrouter/x-ai/grok-4`), and `gemini/gemini-2.5-flash-lite-preview-06-17`. Pattern: rapid model support rotation as new models ship weekly. Maintenance: Aider added these in ~1 week. Source: [github.com/Aider-AI/aider/releases](https://github.com/Aider-AI/aider/releases).
- **OpenHands 1.7.0 (May 1): Session branching + workspace preservation** — `/clear` command creates a new conversation thread that inherits current sandbox and config (preserving runtime state) while starting fresh chat context. Pattern: similar to git branch — fork work without losing state. Enables concurrent exploration. Source: [openhands.org/updates](https://www.openhands.org/updates/).
- **Cursor May updates: Enterprise model governance + Teams delegation** — (1) Enterprise admins can set model allow-lists, soft spend limits with alerts, usage analytics per team/user. (2) Microsoft Teams integration (May 11) lets users mention @Cursor in Teams channels to delegate tasks to cloud agents; Cursor auto-selects repo+model. Pattern: enterprise-grade access control + chat-first workflow. Source: [cursor.com/changelog](https://cursor.com/changelog).
- **Continue.dev MCP expansion** — MCP servers now configurable via JSON (`.continue/mcpServers/` folder), with automatic environment variable templating and intelligent transport selection. Pattern: mirrors Claude's native MCP support (app/mcp_manager.py:251-318 already implements this). Competitive parity on config format. Source: [changelog.continue.dev](https://changelog.continue.dev/).
- **Open-Interpreter Computer API + Anthropic `--os`** — Computer API improvements: 5x launch speed, local vision model for GUI understanding. `--os` flag powered by Anthropic's computer-use capability (screenpipe integration for environment introspection). Pattern: native computer control, mirrors Claude Code's computer-use tools. Source: [github.com/OpenInterpreter/open-interpreter/releases](https://github.com/OpenInterpreter/open-interpreter/releases).
- **Devin 2.2 QA + screen recording** — After PR generation, agent runs app on its Linux desktop, clicks through user flows, records with pass/fail summary cards. Pattern: end-to-end testing with visual proof. 3x faster startup; new UI unifies dev lifecycle (start → review → jump back in). Source: [cognition.ai/blog/introducing-devin-2-2](https://cognition.ai/blog/introducing-devin-2-2).

### Implications for Ai_computer

- **Model ecosystem churn is real**: New models (Gemini-2.5-Flash-Lite, Grok-4) ship weekly; Aider added support in ~1 week. AI_computer's hardcoded vision model detection (lines 818-820 in providers.py) will lag. Low immediate risk (fallback models work), but strategic: competitors move faster. Recommend adding a "latest model" auto-discovery check at startup (scrape openrouter/together model list).
- **Enterprise governance is a feature gap**: Cursor offers model allow-lists, spend limits, and usage analytics per team. AI_computer is currently single-user with no cost controls or model restrictions. Adding `ALLOWED_MODELS` env var (whitelist) + `/api/usage` endpoint (cost tracking) would unlock enterprise use cases. Tier-2 priority but non-trivial (~30–40 LOC).
- **MCP configuration parity achieved**: Continue.dev's JSON config format for MCP matches AI_computer's existing `workspace/mcp_servers.{json,local.json}` approach (plus Continue added auto env-var templating, which is nice-to-have). No feature gap here.
- **Session branching (OpenHands) vs serial task list**: OpenHands allows concurrent exploration (fork session, preserve state). AI_computer is single-task serial with a historical task list. No blocker for feature parity (SSE supports multiple subscriptions), but UX would require significant redesign. Defer until after Phase F (UI split).
- **Computer-use integration is foundational**: Both Devin (desktop testing) and Open-Interpreter rely on native computer control. AI_computer has no desktop execution layer yet (only agent orchestration). Devin's QA + screen recording is aspirational but requires the infrastructure. Pair with a future "agent desktop executor" initiative.


## 2026-05-16 — Codebase patterns

Scanned two random `app/*.py` files end-to-end: `app/tools.py` (1734 lines) and `app/desktop_bridge.py` (289 lines).

- **Dual-mode action dispatch (desktop vs background browser)** — `ToolExecutor.run_action()` (line 1410) routes each action to either background browser handlers (`_*_bg` variants, async) or native desktop handlers. Background mode requires `self._background_mode=True` and `self._bg_browser.is_running`. Pattern: single dispatcher with dual implementations; no cross-mode state sharing. Source: `app/tools.py:1380-1410, 1435-1490`.
- **Isolated window control via Win32 messaging** — `_mouse_click_isolated()` (lines 330–377) converts viewport coords to client coords via `ScreenToClient`, then posts WM_LBUTTONDOWN/UP via `PostMessage` instead of direct automation. Hung window detection via `_is_hung_app_window()` (lines 42–50) uses undocumented `ctypes.windll.user32.IsHungAppWindow` as fallback. Pattern: message-based control is slower but safer for unresponsive apps. Risk: `PostMessage` is async; no ACK. Trade-off: used for isolated targets only (not main desktop). Source: `app/tools.py:330-377, 42-50`.
- **DPI awareness initialization (multi-attempt)** — `_init_dpi_awareness()` (lines 57–65) tries `SetProcessDpiAwareness(2)` (per-monitor) then falls back to `SetProcessDPIAware()` (system-wide). Called at module load (line 70). Pattern: graceful degradation for OS/pywin32 build variations. Side effect: module-level call means failure is silent but coordinates may mismatch on HiDPI. Source: `app/tools.py:57-70`.
- **Clipboard-based large text injection for isolated windows** — `_keyboard_type_isolated()` (lines 304–328) tries path paste, then clipboard paste via `_paste_via_clipboard(isolated=True)`, then falls back to char-by-char `WM_CHAR` PostMessage. Rationale: clipboard is 100x faster than 1000 PostMessage calls. Pattern: silent fallback chain with no user visibility into which path was used. Source: `app/tools.py:304-328, 287-303`.
- **Thread-safe desktop bridge with snapshot-restore for companion mode** — `DesktopBridge` (lines 1–288) uses RLock on all state mutations. Window transitions (maximize→companion resize→restore) are guarded by `time.sleep(0.05–0.08)` between operations (lines 196–210). Snapshot captured before entering companion (line 195); restored on exit with state replay (lines 233–246). Pattern: state machine via sleep-guarded transitions; no async or event-driven coordination. Risk: fixed sleeps are fragile on slow systems. Source: `app/desktop_bridge.py:84-288, 195-246`.
- **Overlay windows for visual feedback in companion mode** — `_create_overlays()` (lines 257–283) spawns 4 frameless webview windows (top/left/right/bottom edges) with animated gradient + glow via CSS keyframes. Overlays are transparent, non-interactive (`easy_drag=False`), and destroyed on companion exit (lines 285–291). Pattern: visual chrome via native windows rather than DOM overlay; browser agnostic. Trade-off: 4 windows × pywebview overhead; no damage region culling. Source: `app/desktop_bridge.py:11-54, 257-291`.
- **SSRF protection via allowlist + IP range validation** — `_validate_public_http_url()` (lines 92–136) blocks schemes other than http(s), rejects private IPs (loopback, 169.254.*, fd00:ec2::254), and blocks hostnames matching ["localhost", "metadata.google.internal", etc.]. Pattern: two-tier: exact match set + substring search. Limitation: no CIDR support; hardcoded blocklist. Source: `app/tools.py:92-136`.
- **Action type mapping via dict handlers with plugin fallback** — `run_action()` handler dict (lines 1493–1552) maps ActionType enum to lambdas; if not found and `plugin_registry` exists, queries `plugin_registry.handlers()` (line 1554). Pattern: extensible dispatch without subclassing. Risk: no validation that plugin handlers return ToolResult; errors wrapped generically. Source: `app/tools.py:1493-1560`.

### Implications for Ai_computer

- **Dual-mode dispatch introduces subtle test gaps**: Background browser handlers use `await self._bg_browser.*`, while desktop handlers use synchronous pyautogui. A test that passes in background mode may fail in desktop mode (and vice versa) due to timing differences or missing state init. Recommend: add a `@pytest.mark.parametrize` test suite that runs the same action sequence in both modes and asserts identical ToolResult output (ignoring output text).
- **Win32 message-based control is fragile on slower systems**: Fixed 50ms delays in `_keyboard_type_isolated` (line 322) and fixed 50–100ms in `_mouse_click_isolated` may cause race conditions if the target window is slow to respond. Recommend: add adaptive delays (check window readiness before next message) or use proper IPC (UI Automation COM, SetTimer).
- **Sleep-based window transitions are a latency/reliability trade-off**: Companion mode relies on `time.sleep(0.05–0.08)` between resize/move/maximize calls (lines 196–210). On heavily loaded systems, these may be insufficient, leading to visual glitches or state corruption. Recommend: use webview event callbacks (if available) or poll for state changes rather than fixed sleeps.
- **Clipboard paste assumes available system clipboard**: `_paste_via_clipboard()` on isolated windows may fail if the clipboard is locked by another process or if the target app forbids clipboard access. No fallback for this specific failure mode; reverts to slow char-by-char PostMessage. Recommend: add a retry loop with exponential backoff, or detect clipboard-locked errors and surface them to the user.
- **SSRF allowlist is maintenance-heavy**: New cloud metadata endpoints (e.g., Oracle metadata on 169.254.169.254/16) will be missed. The hardcoded blocklist is checked once at validation time, not cached. Recommend: externalize the blocklist to a JSON file (`workspace/ssrf_blocklist.json`) and reload it at startup, allowing users to extend it for private clouds.
- **Plugin handler errors have generic traces**: Plugin exception handling (line 1561) wraps all errors as `ToolResult(ok=False, output=f"Plugin error: {str(e)}")`. Multi-line tracebacks are lost. Recommend: log the full traceback to the agent's error log, return only the summary to ToolResult.ok/output.



## 2026-05-17 — Tech radar (FastAPI/SSE/asyncio patterns, LLM provider features)

- **MCP watchdog timer with polling-based health detection** — `_watchdog()` (mcp_manager.py:162-173) polls every 1s; if `_pending` dict is non-empty and no response arrives for 15s (`_WATCHDOG_TIMEOUT`), marks server dead and cancels listener. Pattern: fixed 1s polling interval for responsiveness, 15s threshold avoids false positives on slow requests. Trade-off: 15 one-second sleeps per unresponsive server before detection. Pairs with `_last_response_at` timestamp updated on each successful parse (line 142). Source: `app/mcp_manager.py:17-18, 162-173, 142`.
- **Provider fallback info events via SSE** — `stream_chat_with_tools()` yields `{"type": "provider_info", "model": "...", "fallback": true}` when model fallback activates (line 1242). Gives client real-time visibility into which LLM is actually handling the request. Pattern: transparent model routing; user/agent can log or alert on fallback. Source: `app/providers.py:1240-1242`.
- **Model allowlisting via whitelist filtering** — `_get_allowed_models()` parses `ALLOWED_MODELS` env var (frozenset), then `_openrouter_models_to_try()` filters fallback chain in-place (lines 937-943). Raises ValueError if all models are blocked. Pattern: single-pass filter at planning time, no per-request overhead. Limitation: env var is read once at startup; dynamic allow-list changes require restart. Source: `app/providers.py:423-428, 937-943`.
- **Parallel tool call accumulation via per-index dict** — `stream_chat_with_tools()` accumulates tool calls in `tool_calls_accum[idx]` dict (lines 1285-1360). Each index maintains {id, name, args_buffer} separately; on `finish_reason=tool_calls`, emits all in sorted order. Robust pattern for multi-tool responses, but increases memory footprint if response is very long (args_buffer unbounded until finish). Source: `app/providers.py:1285-1360`.
- **Configurable SSE keepalive timeout via query param** — Per PM notes (IDEA-2026-05-10-01), `/api/tasks/{task_id}/stream` now accepts `?keepalive_timeout_seconds=X` query param; server-side capped [5s, 300s]. Default 30s unchanged. Pattern: per-request tuning without code change; good for slow networks. Source: Git commit `c6747a2`; implementation in app/main.py:~870-914 (not directly visible in providers.py read).
- **Hybrid memory retrieval with reinforcement boost** — `recall_sessions()` combines cosine (0.6 weight) + BM25 (0.4 weight) + temporal decay (exp, 30-day half-life) + reinforcement (log-scaled boost for recall_count) + MMR re-rank (Jaccard, λ=0.7). After recall, increments recall_count in metadata (lines 426-439). Pattern: multi-factor scoring with persistence; encourages useful memories. Limitation: metadata mutations happen in `collection.update()` which may fail silently (wrapped in try/except line 438). Source: `app/memory.py:369-461`.
- **O(n²) consolidation as manual trigger (not yet background)** — `consolidate()` (memory.py:465-570) clusters session summaries via Jaccard ≥0.88, merges, and prunes stale items. Called via `maybe_auto_consolidate()` on `add_action_result()` if counter reaches 50. Pattern: synchronous, full-scan deduplication. Per PM notes (IDEA-2026-05-13-01), consolidation was moved to background task (git commit `201f07c`), but current code still has synchronous version. Trade-off: background task avoids blocking agent loop, but requires coordination (e.g., preventing concurrent consolidations). Source: `app/memory.py:465-570, 572-577`.

### Implications for Ai_computer

- **MCP watchdog adds observability but has 15s latency**: A stalled subprocess (e.g., hung on a syscall) won't be detected for up to 30s (1s poll + 15s timeout + 1s margin). For critical long-running tool calls (e.g., large file transfers), consider exposing watchdog timeout as a tunable parameter (e.g., `?mcp_timeout=5s` in requests) so callers can tighten detection for latency-sensitive workflows.
- **Provider fallback is now transparent but routing is still non-deterministic**: The `provider_info` event helps, but if the first model rate-limits mid-stream, the client sees the transition. For reproducibility and cost tracking, consider logging the final model to a persistent audit log (e.g., `workspace/provider_audit.jsonl`) so the agent can query "which model served request X?" after the fact.
- **ALLOWED_MODELS env var is coarse-grained**: The current frozenset match is exact-string only (lines 937-939 filter `m in allowed`). A user who sets `ALLOWED_MODELS="claude-*"` will block ALL Claude models because no wildcard support exists. Recommend implementing glob pattern matching (fnmatch stdlib) so `ALLOWED_MODELS="claude-*,gpt-4o"` works intuitively. IDEA-2026-05-15-02 is queued for this but not yet done.
- **Parallel tool calls accumulate args in unbounded buffer**: If a streaming response yields 100 parallel tool calls with large arguments (e.g., 10KB each), `args_buffer` can consume 1MB memory before `finish_reason` arrives. No warning or backpressure. For safety, consider capping cumulative args per response or emitting partial tool calls mid-stream.
- **Consolidation was moved to background but sync version still in code**: Git history shows IDEA-2026-05-13-01 merged (commit `201f07c`), but reading current memory.py shows no explicit `asyncio.create_task()` for consolidation. Recommend: (a) verify `201f07c` actually landed and is in HEAD, or (b) if reverted, re-merge with test coverage to ensure background consolidation doesn't corrupt the memory store.
- **Reinforcement boost is silent on update failure**: If `collection.update()` fails to increment `recall_count` (e.g., Chroma is offline), the scoring will re-boost the same memory forever, leading to artificially high recall counts on next consolidation. Recommend: log at WARN level if metadata update fails, or cascade the failure to the caller so they can see degraded memory state.
