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
