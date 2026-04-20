import pytest
import asyncio
import json
import importlib
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app, API_KEY
from app.memory import MemoryStore, _FallbackCollection
from app.safety import SafetyManager
from app.models import Action, ActionType, DangerLevel
from app.tools import ToolExecutor
from app.agent import AgentService

# Create workspace dir for tests
workspace = Path("test_workspace").resolve()
workspace.mkdir(exist_ok=True)

# Test 1: MemoryStore fallback
def test_memorystore_fallback():
    # Force fallback by passing an invalid path that chromadb can't write to, 
    # or just use the mock if needed. Actually we can mock chromadb import.
    with patch.dict("sys.modules", {"chromadb": None}):
        store = MemoryStore(workspace / "test_db")
        assert isinstance(store.collection, _FallbackCollection)
        
        store.add("test_kind", "This is a test of fallback search")
        store.add("test_kind", "Another unrelated document")
        
        results = store.search("fallback search")
        assert len(results) > 0
        assert "fallback" in results[0].content.lower()

# Test 2: SafetyManager classifies run_command as high-risk
def test_safetymanager_high_risk():
    safety = SafetyManager()
    action = Action(id="1", type=ActionType.run_command, args={"command": "echo test"})
    decision = safety.evaluate(action)
    assert decision.danger == DangerLevel.high
    assert decision.requires_approval is True

# Test 3: SafetyManager hard-blocks dangerous shell commands
def test_safetymanager_hard_block():
    safety = SafetyManager()
    action = Action(id="2", type=ActionType.run_command, args={"command": "rm -rf /"})
    decision = safety.evaluate(action)
    assert decision.danger == DangerLevel.high
    assert "Hard-blocked" in decision.reason
    assert decision.requires_approval is True

# Test 4: ToolExecutor text_create and text_view via tmp_path workspace
def test_toolexecutor_text_tools():
    import uuid
    filename = f"test_file_{uuid.uuid4().hex}.txt"
    tools = ToolExecutor(workspace)
    
    # Create
    res = tools.text_editor.create(filename, "Line 1\nLine 2")
    assert res.ok
    assert (workspace / filename).exists()
    
    # View
    res = tools.text_editor.view(filename)
    assert res.ok
    assert "Line 1" in res.output

# Test 5: TextEditorTool.str_replace raises ToolError when old_str not found
def test_toolexecutor_str_replace_error():
    import uuid
    filename = f"test_file2_{uuid.uuid4().hex}.txt"
    tools = ToolExecutor(workspace)
    tools.text_editor.create(filename, "Hello world")
    
    with pytest.raises(Exception):
        tools.text_editor.str_replace(filename, "not_found", "replacement")

# Test 6: plan_hierarchical returns valid HierarchicalPlan
@patch("app.providers.PlannerProvider._chat_anthropic")
def test_plan_hierarchical(mock_chat):
    mock_chat.return_value = '{"reasoning": "test", "sub_tasks": [{"id": "1", "description": "st1", "actions": []}], "overall_complete": false}'
    
    from app.providers import PlannerProvider
    provider = PlannerProvider()
    provider._anthropic_key = "test"
    plan = provider.plan_hierarchical("test goal")
    assert plan.reasoning == "test"
    assert len(plan.sub_tasks) == 1

# Test 6b: plan_hierarchical repairs action-shaped sub_tasks from weaker models
@patch("app.providers.PlannerProvider._chat_anthropic")
def test_plan_hierarchical_repairs_action_entries(mock_chat):
    mock_chat.return_value = """{
        "reasoning": "test",
        "sub_tasks": [
            {"id": "sysinfo", "type": "system_info", "args": {}, "explanation": "Get system information", "requires_approval": false},
            {"id": "write-file", "type": "write_file", "args": {"path": "hello.py", "content": "print('hi')"}, "explanation": "Write hello.py", "requires_approval": false}
        ],
        "overall_complete": false
    }"""

    from app.providers import PlannerProvider
    provider = PlannerProvider()
    provider._anthropic_key = "test"
    plan = provider.plan_hierarchical("test goal")

    assert len(plan.sub_tasks) == 2
    assert plan.sub_tasks[0].description == "Get system information."
    assert plan.sub_tasks[0].actions[0].type == ActionType.system_info
    assert plan.sub_tasks[1].actions[0].type == ActionType.write_file


# Test 6c: plan_hierarchical fills missing descriptions for otherwise valid sub_tasks
@patch("app.providers.PlannerProvider._chat_anthropic")
def test_plan_hierarchical_fills_missing_descriptions(mock_chat):
    mock_chat.return_value = """{
        "reasoning": "test",
        "sub_tasks": [
            {"id": "1", "actions": [{"id": "run-test", "type": "run_command", "args": {"command": "python hello.py"}, "explanation": "Run hello.py", "requires_approval": false}]}
        ]
    }"""

    from app.providers import PlannerProvider
    provider = PlannerProvider()
    provider._anthropic_key = "test"
    plan = provider.plan_hierarchical("test goal")

    assert len(plan.sub_tasks) == 1
    assert plan.sub_tasks[0].description == "Run hello.py."
    assert plan.sub_tasks[0].actions[0].type == ActionType.run_command


def test_extract_chat_message_text_supports_string_content():
    from app.providers import _extract_chat_message_text

    payload = {"choices": [{"message": {"content": '{"ok": true}'}}]}
    assert _extract_chat_message_text(payload) == '{"ok": true}'


def test_extract_chat_message_text_supports_list_content():
    from app.providers import _extract_chat_message_text

    payload = {
        "choices": [
            {
                "message": {
                    "content": [
                        {"type": "text", "text": '{"reasoning": "r"'},
                        {"type": "text", "text": ', "overall_complete": false}'},
                    ]
                }
            }
        ]
    }
    assert _extract_chat_message_text(payload) == '{"reasoning": "r"\n, "overall_complete": false}'


def test_extract_chat_message_text_raises_clear_error_without_choices():
    from app.providers import _extract_chat_message_text

    with pytest.raises(RuntimeError, match="did not include choices"):
        _extract_chat_message_text({"error": {"message": "Upstream model error"}})

# Test 7: key_combo calls pyautogui.hotkey
@patch("pyautogui.hotkey")
def test_key_combo(mock_hotkey):
    tools = ToolExecutor(workspace)
    action = Action(id="3", type=ActionType.key_combo, args={"keys": "ctrl+c"})
    # run_action is async
    res = asyncio.run(tools.run_action(action))
    assert res.ok
    mock_hotkey.assert_called_once_with("ctrl", "c")

# Test 8: Agent action limit 50
@pytest.mark.asyncio
async def test_agent_action_limit():
    from app.log_emitter import log_emitter
    service = AgentService(workspace, log_emitter=log_emitter)
    record = service.init_task("task_1", "goal")
    
    # Mock planner to return 51 actions
    with patch("app.providers.PlannerProvider.plan_hierarchical") as mock_plan:
        from app.models import HierarchicalPlan, SubTask, Action
        actions = [Action(id=str(i), type=ActionType.wait_action, args={"seconds": 0}) for i in range(51)]
        mock_plan.return_value = HierarchicalPlan(
            reasoning="test",
            sub_tasks=[SubTask(id="1", description="desc", actions=actions)],
            overall_complete=False
        )
        
        with patch("app.providers.PlannerProvider.reflect_on_subtask", return_value={"success": True}):
            with patch("app.providers.PlannerProvider.evaluate", return_value={"complete": True}):
                await service.run_task("task_1", "goal")
                
                # Verify error was emitted
                # The queue should have the error message
                import json
                log_path = Path("workspace/logs/task_1.jsonl")
                assert log_path.exists()
                log_content = log_path.read_text()
                assert "Hard limit of 50 actions reached" in log_content

# Test 9: SSE event field names verify
@pytest.mark.asyncio
async def test_empty_plan_finishes_as_blocked_without_evaluation():
    from app.log_emitter import log_emitter
    from app.models import HierarchicalPlan

    task_id = "blocked_task"
    log_path = Path(f"workspace/logs/{task_id}.jsonl")
    log_path.unlink(missing_ok=True)

    service = AgentService(workspace, log_emitter=log_emitter)

    with patch("app.providers.PlannerProvider.plan_hierarchical") as mock_plan:
        mock_plan.return_value = HierarchicalPlan(
            reasoning="Providing code for this request is disallowed under policy.",
            sub_tasks=[],
            overall_complete=False,
        )
        with patch("app.providers.PlannerProvider.evaluate") as mock_evaluate:
            await service.run_task(task_id, "blocked goal")
            mock_evaluate.assert_not_called()

    assert log_path.exists()
    log_content = log_path.read_text(encoding="utf-8")
    assert '"blocked": true' in log_content
    assert "disallowed under policy" in log_content
    assert "Evaluating results" not in log_content

def test_sse_event_fields():
    from app.log_emitter import log_emitter
    q = log_emitter.subscribe("test_task")
    log_emitter.emit("test_task", "status", {"message": "test"})
    msg = q.get_nowait()
    assert msg["type"] == "status"
    assert msg["message"] == "test"


def test_sse_reasoning_event_fields():
    from app.log_emitter import log_emitter
    q = log_emitter.subscribe("reasoning_task")
    log_emitter.emit(
        "reasoning_task",
        "reasoning",
        {
            "stage": "Planning",
            "summary": "Plan ready",
            "detail": "Prepared 3 sub-tasks.",
            "live": False,
        },
    )
    msg = q.get_nowait()
    assert msg["type"] == "reasoning"
    assert msg["stage"] == "Planning"
    assert msg["summary"] == "Plan ready"

# FastAPI TestClient
client = TestClient(app)
headers = {"Authorization": f"Bearer {API_KEY}"}

# Test 10: GET /api/health
def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert "uptime_seconds" in response.json()
    assert response.json()["status"] == "ok"


def test_frontend_routes():
    root = client.get("/")
    assert root.status_code == 200
    assert "text/html" in root.headers["content-type"]

    v2 = client.get("/v2")
    assert v2.status_code == 200
    assert "text/html" in v2.headers["content-type"]
    assert "Single-stream workspace" in v2.text

# Test 11: GET /api/models
def test_models():
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test"}):
        response = client.get("/api/models")
        assert response.status_code == 200
        assert "claude-3-5-sonnet-20241022" in response.json()["models"]

# Test 12: POST /api/tasks
def test_post_tasks():
    import app.main as mainmod
    mainmod._tasks.clear()
    mainmod.service._active_tasks.clear()
    response = client.post("/api/tasks", json={"task_id": "test_1", "goal": "test goal"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_post_tasks_rejects_duplicate_active_id():
    import app.main as mainmod
    mainmod._tasks.clear()
    mainmod.service._active_tasks.clear()
    with patch("app.main.service.init_task") as mock_init:
        from app.models import TaskRecord, AgentContext
        mock_init.return_value = TaskRecord(id="dup_task", status="running", context=AgentContext(goal="test goal"), goal="test goal")

        first = client.post("/api/tasks", json={"task_id": "dup_task", "goal": "test goal"}, headers=headers)
        assert first.status_code == 200

        second = client.post("/api/tasks", json={"task_id": "dup_task", "goal": "test goal"}, headers=headers)
        assert second.status_code == 409
        assert "already exists" in second.json()["detail"]


def test_post_tasks_rejects_invalid_mode():
    response = client.post(
        "/api/tasks",
        json={"task_id": "bad_mode", "goal": "test goal", "mode": "wizard_mode"},
        headers=headers,
    )
    assert response.status_code == 422


def test_download_task_log():
    log_path = Path("workspace/logs/download_me.jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text('{"type":"status","message":"ok"}\n', encoding="utf-8")
    response = client.get("/api/tasks/download_me/log/download", headers=headers)
    assert response.status_code == 200
    assert "attachment" in response.headers.get("content-disposition", "")


def test_retry_task():
    import app.main as mainmod
    from app.models import TaskRecord, AgentContext

    with patch("app.main.service.init_task") as mock_init:
        mainmod._tasks["retry_source"] = TaskRecord(
            id="retry_source",
            status="done",
            context=AgentContext(goal="test retry"),
            goal="test retry",
            model="openrouter/nvidia/nemotron-3-super-120b-a12b:free",
            mode="coding",
        )
        mock_init.return_value = TaskRecord(
            id="retry_source-retry-123",
            status="running",
            context=AgentContext(goal="test retry"),
            goal="test retry",
            model="openrouter/nvidia/nemotron-3-super-120b-a12b:free",
            mode="coding",
        )

        response = client.post("/api/tasks/retry_source/retry", headers=headers)
        assert response.status_code == 200
        assert response.json()["retried_from"] == "retry_source"
        assert response.json()["task_id"].startswith("retry_source-retry-")
        mainmod._tasks.pop("retry_source", None)


def test_persisted_task_records_reload_incomplete_as_failed(monkeypatch):
    task_dir = Path("workspace/tasks")
    task_dir.mkdir(parents=True, exist_ok=True)
    record_path = task_dir / "persisted_reload.json"
    record_path.write_text(
        json.dumps(
            {
                "id": "persisted_reload",
                "status": "running",
                "context": {"goal": "persisted goal", "history": [], "screen_width": 1280, "screen_height": 800},
                "goal": "persisted goal",
                "created_at": "2026-04-19T00:00:00+00:00",
                "model": "gpt-4o-mini",
                "mode": "coding",
            }
        ),
        encoding="utf-8",
    )

    import app.main as mainmod
    importlib.reload(mainmod)

    record = mainmod._tasks["persisted_reload"]
    assert record.status == "failed"
    assert "restarted" in (record.reason or "").lower()

    record_path.unlink(missing_ok=True)


def test_stream_since_replays_only_new_events(tmp_path):
    log_path = Path("workspace/logs/stream_cursor.jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        '\n'.join(
            [
                '{"type":"status","message":"first"}',
                '{"type":"status","message":"second"}',
                '{"type":"done","complete":true,"reason":"ok"}',
            ]
        ) + '\n',
        encoding="utf-8",
    )

    response = client.get(f"/api/tasks/stream_cursor/stream?token={API_KEY}&since=1")
    assert response.status_code == 200
    body = response.text
    assert '"message": "first"' not in body
    assert '"message": "second"' in body
    assert '"type": "done"' in body


def test_stream_replays_reasoning_events():
    log_path = Path("workspace/logs/reasoning_cursor.jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        '\n'.join(
            [
                '{"type":"reasoning","stage":"Planning","summary":"Plan ready","detail":"Prepared 2 steps.","live":false}',
                '{"type":"done","complete":true,"reason":"ok"}',
            ]
        ) + '\n',
        encoding="utf-8",
    )

    response = client.get(f"/api/tasks/reasoning_cursor/stream?token={API_KEY}")
    assert response.status_code == 200
    body = response.text
    assert '"type": "reasoning"' in body
    assert '"summary": "Plan ready"' in body


def test_retry_task_uses_persisted_record():
    import app.main as mainmod

    mainmod._tasks.pop("persisted_retry", None)
    record_path = Path("workspace/tasks/persisted_retry.json")
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(
        json.dumps(
            {
                "id": "persisted_retry",
                "status": "done",
                "context": {"goal": "retry persisted", "history": [], "screen_width": 1280, "screen_height": 800},
                "goal": "retry persisted",
                "created_at": "2026-04-19T00:00:00+00:00",
                "model": "openrouter/nvidia/nemotron-3-super-120b-a12b:free",
                "mode": "coding",
            }
        ),
        encoding="utf-8",
    )

    with patch("app.main.service.init_task") as mock_init:
        from app.models import TaskRecord, AgentContext

        mock_init.return_value = TaskRecord(
            id="persisted_retry-retry-123",
            status="running",
            context=AgentContext(goal="retry persisted"),
            goal="retry persisted",
            model="openrouter/nvidia/nemotron-3-super-120b-a12b:free",
            mode="coding",
        )

        response = client.post("/api/tasks/persisted_retry/retry", headers=headers)
        assert response.status_code == 200
        assert response.json()["retried_from"] == "persisted_retry"

    record_path.unlink(missing_ok=True)

# Test 13: DELETE /api/tasks/{task_id}
def test_delete_tasks():
    # Make sure we use a mock for AgentService.cancel_task to avoid async timing issues
    with patch("app.main.service.cancel_task", return_value=True):
        client.post("/api/tasks", json={"task_id": "test_2", "goal": "test goal"}, headers=headers)
        response = client.delete("/api/tasks/test_2", headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"
