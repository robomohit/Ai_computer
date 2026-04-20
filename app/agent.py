from __future__ import annotations
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .background_browser import BackgroundBrowser
from .log_emitter import LogEmitter
from .memory import MemoryStore
from .models import (
    Action,
    ActionDecision,
    ActionType,
    AgentContext,
    ApprovalBundle,
    TaskRecord,
    ToolError,
    ToolResult,
)
from .permissions import PermissionStore, scope_for_action
from .providers import PlannerProvider, _capture_screenshot_b64, detect_task_mode
from .safety import SafetyManager
from .text_editor import TextEditorTool
from .tools import ToolExecutor
from .plugins import PluginRegistry

_log = logging.getLogger("agent")

_SCREENSHOT_ACTIONS = {
    ActionType.mouse_click,
    ActionType.keyboard_type,
    ActionType.scroll,
    ActionType.double_click,
    ActionType.right_click,
    ActionType.middle_click,
    ActionType.mouse_move,
    ActionType.left_click_drag,
    ActionType.key_combo,
}


class AgentService:
    def __init__(self, workspace: Path, log_emitter: LogEmitter):
        self.workspace = workspace
        self.log_emitter = log_emitter
        self.memory = MemoryStore(workspace)
        self.safety = SafetyManager()
        self.permissions = PermissionStore()
        self.plugin_registry = PluginRegistry()
        self.plugin_registry.load_defaults()
        self.tools = ToolExecutor(workspace, plugin_registry=self.plugin_registry)
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._paused_tasks: set[str] = set()
        self._approvals: Dict[str, asyncio.Future] = {}
        self._permission_waits: Dict[str, asyncio.Future] = {}
        self._pause_events: Dict[str, asyncio.Event] = {}
        self._on_task_complete: Optional[Callable[[str, str, str], None]] = None
        # Per-task background browsers (for computer_use cowork mode)
        self._bg_browsers: Dict[str, BackgroundBrowser] = {}

    async def _emit(self, task_id: str, event: str, data: Dict[str, Any]):
        """Emit an SSE event and yield control so the event loop can flush it to clients."""
        self.log_emitter.emit(task_id, event, data)
        await asyncio.sleep(0)  # yield to event loop — lets SSE generator send this event immediately

    async def _emit_reasoning(
        self,
        task_id: str,
        stage: str,
        summary: str,
        detail: str = "",
        *,
        live: bool = False,
        elapsed_seconds: Optional[int] = None,
    ) -> None:
        payload: Dict[str, Any] = {
            "stage": stage,
            "summary": summary,
            "detail": detail,
            "live": live,
        }
        if elapsed_seconds is not None:
            payload["elapsed_seconds"] = elapsed_seconds
        await self._emit(task_id, "reasoning", payload)

    async def _run_with_phase_updates(
        self,
        task_id: str,
        waiting_message: str,
        progress_label: str,
        fn: Callable[..., Any],
        *args: Any,
        timeout: float = 120.0,
        heartbeat_interval: float = 1.0,
    ) -> Any:
        await self._emit(task_id, "status", {"message": waiting_message})
        await self._emit_reasoning(
            task_id,
            progress_label,
            waiting_message,
            "Working through the next model step.",
            live=True,
            elapsed_seconds=0,
        )
        work = asyncio.create_task(asyncio.to_thread(fn, *args))
        start = asyncio.get_running_loop().time()
        last_heartbeat = start - heartbeat_interval
        while not work.done():
            await asyncio.sleep(heartbeat_interval)
            if work.done():
                break
            now = asyncio.get_running_loop().time()
            elapsed = int(now - start)
            if elapsed >= timeout:
                work.cancel()
                raise TimeoutError(f"{progress_label} timed out after {elapsed}s. Try a different model if this keeps happening.")
            if now - last_heartbeat >= heartbeat_interval:
                await self._emit(
                    task_id,
                    "status",
                    {
                        "message": f"{progress_label}... {elapsed}s elapsed",
                        "elapsed_seconds": elapsed,
                        "heartbeat": True,
                    },
                )
                await self._emit_reasoning(
                    task_id,
                    progress_label,
                    progress_label,
                    "Still waiting on the model response.",
                    live=True,
                    elapsed_seconds=elapsed,
                )
                last_heartbeat = now
        return await work

    def init_task(
        self,
        task_id: str,
        goal: str,
        screen_width: int = 1280,
        screen_height: int = 800,
        model: str = "claude-3-5-sonnet-20241022",
        mode: str = "auto",
    ) -> TaskRecord:
        detected_mode = detect_task_mode(goal, mode if mode != "auto" else None)
        context = AgentContext(
            goal=goal,
            screen_width=screen_width,
            screen_height=screen_height,
        )
        record = TaskRecord(id=task_id, status="running", context=context, goal=goal)
        record.model = model
        record.mode = detected_mode
        self._active_tasks[task_id] = asyncio.create_task(
            self.run_task(task_id, goal, screen_width, screen_height, model, detected_mode)
        )
        return record

    async def run_task(
        self,
        task_id: str,
        goal: str,
        screen_width: int = 1280,
        screen_height: int = 800,
        model: str = "claude-3-5-sonnet-20241022",
        mode: str = "coding",
    ):
        provider = PlannerProvider(model=model)
        is_coding = mode == "coding"
        is_computer_use = mode == "computer_use"
        is_desktop = mode == "computer"  # only this mode takes over the real screen

        # Determine whether this task runs in the background (cowork) or takes
        # over the desktop.  Coding and computer_use are always background.
        runs_in_background = is_coding or is_computer_use

        # Brief delay so the SSE EventSource in the browser has time to connect
        # before we start emitting events (prevents the race where events fire
        # before the frontend subscription is established)
        await asyncio.sleep(0.3)

        await self._emit(task_id, "status", {"message": f"Initializing planning... (mode: {mode})"})
        await self._emit(task_id, "mode", {"mode": mode})
        await self._emit_reasoning(
            task_id,
            "Setup",
            "Preparing the workspace",
            f"Detected mode: {mode}. Loading context, permissions, and execution tools.",
        )

        # Tell the frontend whether the agent is working in the background
        await self._emit(task_id, "cowork_status", {
            "background": runs_in_background,
            "message": (
                "Agent is working in the background — your computer is free to use."
                if runs_in_background
                else "Agent needs your screen. It will control the mouse & keyboard."
            ),
        })

        # For computer_use mode, spin up a headless Playwright browser so all
        # browser interactions happen invisibly, without touching the user's
        # real desktop.
        bg_browser: Optional[BackgroundBrowser] = None
        if is_computer_use:
            try:
                bg_browser = BackgroundBrowser(width=screen_width, height=screen_height, headless=True)
                await bg_browser.start()
                self._bg_browsers[task_id] = bg_browser
                self.tools.set_background_browser(bg_browser)
                self.tools._background_mode = True
                await self._emit(task_id, "status", {"message": "Background browser ready — working silently."})
            except Exception as exc:
                _log.warning("Could not start background browser: %s — falling back to desktop", exc)
                await self._emit(task_id, "status", {"message": f"Background browser unavailable ({exc}). Using desktop."})
                bg_browser = None
                self.tools._background_mode = False
        elif is_coding:
            # Coding mode never needs GUI at all
            self.tools._background_mode = True
        else:
            # Desktop mode — pyautogui takes over
            self.tools._background_mode = False
        try:
            context_memories = self.memory.search(goal, limit=5)
            memory_context: Optional[str] = None
            if context_memories:
                memory_context = "\n".join(f"- {m.content}" for m in context_memories)

            # In coding mode, auto-discover the environment before planning
            env_context = ""
            if is_coding:
                env_result = self.tools.system_info()
                await self._emit(task_id, "action_result", {
                    "action_id": "auto-env",
                    "ok": env_result.ok,
                    "output": env_result.output,
                })
                env_context = f"\n\nSystem environment:\n{env_result.output}\nUse these EXACT paths in your actions — do NOT use template variables or placeholders."
            
            if is_coding:
                await self._emit_reasoning(
                    task_id,
                    "Setup",
                    "Read local environment",
                    "Captured the exact workspace and system paths before planning edits.",
                )

            # Coding and computer_use modes skip screenshots (DOM/text-only)
            screenshot_b64 = None if (is_coding or is_computer_use) else _capture_screenshot_b64(screen_width, screen_height)

            # Run the sync LLM call in a thread so the event loop stays free for SSE streaming
            plan = await self._run_with_phase_updates(
                task_id,
                "Thinking",
                "Still planning",
                provider.plan_hierarchical,
                goal + env_context,
                screenshot_b64,
                memory_context,
                mode,
            )
            subtask_preview = ", ".join(st.description for st in plan.sub_tasks[:3])
            await self._emit_reasoning(
                task_id,
                "Planning",
                "Plan ready",
                f"Prepared {len(plan.sub_tasks)} sub-tasks." + (f" First steps: {subtask_preview}" if subtask_preview else ""),
            )
            await self._emit(task_id, "plan", plan.model_dump())

            if not plan.sub_tasks:
                reason = plan.reasoning or "No actionable plan was produced."
                summary = "Request blocked" if any(
                    token in reason.lower()
                    for token in ("disallow", "policy", "illicit", "malicious", "unauthorized", "spam", "harassment")
                ) else "No actionable plan"
                await self._emit_reasoning(
                    task_id,
                    "Planning",
                    summary,
                    reason,
                )
                self._finalize(task_id, "failed", reason)
                await self._emit(
                    task_id,
                    "done",
                    {
                        "complete": False,
                        "reason": reason,
                        "blocked": summary == "Request blocked",
                        "finished_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                return

            history: List[str] = []
            action_count = 0
            consecutive_fails = 0

            while plan.sub_tasks:
                sub_task = plan.sub_tasks.pop(0)
                await self._emit(task_id, "status", {"message": f"Executing sub-task: {sub_task.description}"})
                await self._emit(
                    task_id,
                    "subtask",
                    {
                        "subtask_id": sub_task.id,
                        "description": sub_task.description,
                        "status": "running",
                    },
                )
                await self._emit_reasoning(
                    task_id,
                    "Execution",
                    "Starting sub-task",
                    sub_task.description,
                )

                results: List[str] = []
                actions_taken: List[Dict[str, Any]] = []

                for action_data in sub_task.actions:
                    if action_count >= 50:
                        await self._emit(task_id, "error", {"message": "Hard limit of 50 actions reached."})
                        await self._emit(task_id, "done", {"complete": False, "reason": "Hard limit of 50 actions reached."})
                        return
                        
                    while task_id in self._paused_tasks:
                        await asyncio.sleep(0.5)
                        
                    action_count += 1
                    
                    action = Action(**action_data.model_dump())
                    decision = self.safety.evaluate(action, safe_mode=not is_coding)

                    await self._emit(task_id, "action_start", {
                        "action_id": action.id,
                        "action_type": action.type.value,
                        "explanation": action.explanation,
                        "args_summary": _summarize_args(action.type.value, action.args),
                    })
                    await self._emit_reasoning(
                        task_id,
                        "Execution",
                        f"Preparing {action.type.value}",
                        action.explanation or _summarize_args(action.type.value, action.args),
                    )

                    # Handle request_permission specially: ask the user, record grant/deny,
                    # then continue (don't dispatch to tools.py).
                    if action.type == ActionType.request_permission:
                        scope = action.args.get("scope", "")
                        reason = action.args.get("reason", action.explanation or "")
                        if self.permissions.is_granted(task_id, scope):
                            res = ToolResult(ok=True, output=f"Permission for '{scope}' already granted.")
                        else:
                            await self._emit(task_id, "permission_required", {
                                "action_id": action.id,
                                "scope": scope,
                                "reason": reason,
                                "explanation": action.explanation,
                            })
                            granted = await self._wait_for_permission(task_id, action.id)
                            if granted:
                                self.permissions.grant(task_id, scope)
                                res = ToolResult(ok=True, output=f"Permission granted for scope '{scope}'.")
                            else:
                                self.permissions.deny(task_id, scope)
                                await self._emit(task_id, "status", {"message": f"Permission denied for '{scope}'. Stopping."})
                                self._finalize(task_id, "cancelled", f"user denied permission for scope '{scope}'")
                                await self._emit(task_id, "done", {"complete": False, "reason": f"Permission denied: {scope}"})
                                return
                        results.append(res.output)
                        actions_taken.append(action.model_dump())
                        self.memory.add_action_result(task_id, action.id, res.output)
                        history.append(f"Action: request_permission({scope}) -> {res.output}")
                        await self._emit(task_id, "action_result", {
                            "action_id": action.id,
                            "ok": res.ok,
                            "output": res.output,
                            "action_type": action.type.value,
                            "args_summary": scope,
                        })
                        continue

                    # Enforce permission scope for browser/filesystem/shell actions
                    needed_scope = scope_for_action(action.type.value, action.args)
                    if needed_scope and not self.permissions.is_granted(task_id, needed_scope.value):
                        # Auto-prompt for the scope if the agent forgot to request it
                        await self._emit(task_id, "permission_required", {
                            "action_id": action.id,
                            "scope": needed_scope.value,
                            "reason": f"Action '{action.type.value}' needs '{needed_scope.value}' access.",
                            "explanation": action.explanation,
                        })
                        granted = await self._wait_for_permission(task_id, action.id)
                        if not granted:
                            self.permissions.deny(task_id, needed_scope.value)
                            await self._emit(task_id, "status", {"message": f"Permission denied for '{needed_scope.value}'. Stopping."})
                            self._finalize(task_id, "cancelled", f"user denied permission for scope '{needed_scope.value}'")
                            await self._emit(task_id, "done", {"complete": False, "reason": f"Permission denied: {needed_scope.value}"})
                            return
                        self.permissions.grant(task_id, needed_scope.value)

                    if action.requires_approval or decision.requires_approval:
                        await self._emit(task_id, "approval_required", {
                            "action_id": action.id,
                            "action": action.model_dump(),
                            "danger": decision.danger.value,
                            "reason": decision.reason,
                            "explanation": action.explanation,
                        })
                        approved = await self._wait_for_approval(task_id, action.id)
                        if not approved:
                            await self._emit(task_id, "status", {"message": f"Action {action.id} rejected. Stopping."})
                            self._finalize(task_id, "cancelled", "user rejected action")

                            return

                    # Longer timeout for coding commands (builds can be slow)
                    timeout = 300.0 if is_coding else 120.0
                    async def _stream_chunk(chunk: Dict[str, Any]):
                        await self._emit(task_id, "terminal_output", {
                            "command": action.args.get("command", ""),
                            "output": chunk.get("output", ""),
                            "ok": True,
                            "stream": True,
                            "channel": chunk.get("channel", "stdout"),
                            "action_id": action.id,
                        })
                    try:
                        res = await asyncio.wait_for(
                            self.tools.run_action(action, sw=screen_width, sh=screen_height, on_stream=_stream_chunk),
                            timeout=timeout
                        )
                    except asyncio.TimeoutError:
                        res = ToolResult(ok=False, output=f"Action timed out after {timeout} seconds.")
                    except Exception as e:
                        res = ToolResult(ok=False, output=f"Action failed with exception: {str(e)}")

                    results.append(res.output)
                    actions_taken.append(action.model_dump())

                    self.memory.add_action_result(task_id, action.id, res.output)

                    log_entry = f"Action: {action.type.value} -> {res.output}"
                    history.append(log_entry)
                    await self._emit_reasoning(
                        task_id,
                        "Execution",
                        f"Finished {action.type.value}",
                        (res.output or "")[:220] or "Action completed.",
                    )
                    await self._emit(task_id, "action_result", {
                        "action_id": action.id,
                        "ok": res.ok,
                        "output": res.output,
                        "action_type": action.type.value,
                        "args_summary": _summarize_args(action.type.value, action.args),
                    })

                    # In coding mode, emit file content changes instead of screenshots
                    if is_coding:
                        if action.type.value in ("write_file", "text_create", "text_str_replace", "text_insert"):
                            file_path = action.args.get("path", "")
                            await self._emit(task_id, "file_change", {
                                "path": file_path,
                                "action": action.type.value,
                                "content": action.args.get("content", action.args.get("file_text", "")),
                            })
                        elif action.type.value == "run_command":
                            await self._emit(task_id, "terminal_output", {
                                "command": action.args.get("command", ""),
                                "output": res.output,
                                "ok": res.ok,
                            })
                    elif is_computer_use:
                        # Emit browser-specific UI events so the frontend can show
                        # a mini page-state panel instead of screenshots.
                        if action.type.value == "browser_open":
                            await self._emit(task_id, "browser_event", {
                                "kind": "navigate",
                                "url": action.args.get("url", ""),
                                "result": res.output[:200],
                            })
                        elif action.type.value in ("browser_click", "browser_type", "browser_scroll"):
                            await self._emit(task_id, "browser_event", {
                                "kind": action.type.value,
                                "selector": action.args.get("selector", ""),
                                "result": res.output[:200],
                            })
                        elif action.type.value in ("browser_accessibility_tree", "browser_get_text"):
                            await self._emit(task_id, "browser_event", {
                                "kind": "page_read",
                                "excerpt": res.output[:600],
                            })
                        # Send a screenshot from the background browser so the
                        # user can see what the agent sees — without it touching
                        # the real desktop.
                        if bg_browser and bg_browser.is_running:
                            try:
                                bg_shot = await bg_browser.screenshot_b64()
                                await self._emit(task_id, "screenshot", {"data": bg_shot})
                            except Exception:
                                pass  # non-critical
                    else:
                        if action.type in _SCREENSHOT_ACTIONS or action.type == ActionType.screenshot:
                            screenshot = res.base64_image or _capture_screenshot_b64(screen_width, screen_height)
                            await self._emit(task_id, "screenshot", {"data": screenshot})

                # Reflection — run sync LLM in thread
                reflect_screenshot = None if (is_coding or is_computer_use) else _capture_screenshot_b64(screen_width, screen_height)
                reflection = await self._run_with_phase_updates(
                    task_id,
                    "Reflecting on progress...",
                    "Still reflecting",
                    provider.reflect_on_subtask,
                    sub_task.description,
                    actions_taken,
                    results,
                    reflect_screenshot,
                    mode,
                )
                await self._emit_reasoning(
                    task_id,
                    "Reflection",
                    "Checked sub-task result",
                    reflection.get("reason", "Finished reviewing the last step."),
                )
                await self._emit(task_id, "reflection", reflection)

                if not reflection.get("success", True):
                    await self._emit(
                        task_id,
                        "subtask",
                        {
                            "subtask_id": sub_task.id,
                            "description": sub_task.description,
                            "status": "failed",
                            "reason": reflection.get("reason", ""),
                        },
                    )
                    consecutive_fails += 1
                    retry_actions = reflection.get("retry_actions", [])
                    for retry_data in retry_actions:
                        if action_count >= 50:
                            break
                        action_count += 1
                        if "id" not in retry_data or not retry_data["id"]:
                            retry_data["id"] = str(uuid.uuid4())
                        try:
                            retry_action = Action(**retry_data)
                            retry_res = await asyncio.wait_for(self.tools.run_action(retry_action, sw=screen_width, sh=screen_height), timeout=timeout)
                            self.memory.add_action_result(task_id, retry_action.id, retry_res.output)
                            history.append(f"Retry: {retry_action.type.value} -> {retry_res.output}")
                            await self._emit(
                                task_id,
                                "action_result",
                                {"action_id": retry_action.id, "ok": retry_res.ok, "output": retry_res.output},
                            )
                        except Exception as e:
                            history.append(f"Retry failed: {str(e)}")
                            
                    await self._emit(
                        task_id,
                        "status",
                        {"message": f"Sub-task failed: {reflection.get('reason')}"},
                    )
                    
                    if consecutive_fails > 2:
                        await self._emit(task_id, "status", {"message": "Multiple failures detected. Re-planning..."})
                        await self._emit_reasoning(
                            task_id,
                            "Planning",
                            "Re-planning after repeated failures",
                            "The previous approach did not verify cleanly, so the agent is generating a new path.",
                        )
                        replan_screenshot = None if (is_coding or is_computer_use) else _capture_screenshot_b64(screen_width, screen_height)
                        plan = await self._run_with_phase_updates(
                            task_id,
                            "Re-planning",
                            "Still re-planning",
                            provider.plan_hierarchical,
                            goal + f" (Re-planning after failures. History: {history[-5:]})",
                            replan_screenshot,
                            memory_context,
                            mode,
                        )
                        await self._emit_reasoning(
                            task_id,
                            "Planning",
                            "New plan ready",
                            f"Prepared {len(plan.sub_tasks)} replacement sub-tasks after recovery.",
                        )
                        await self._emit(task_id, "plan", plan.model_dump())
                        consecutive_fails = 0
                else:
                    await self._emit(
                        task_id,
                        "subtask",
                        {
                            "subtask_id": sub_task.id,
                            "description": sub_task.description,
                            "status": "done",
                            "reason": reflection.get("reason", ""),
                        },
                    )
                    consecutive_fails = 0

            # Final Evaluation — run sync LLM in thread
            await self._emit_reasoning(
                task_id,
                "Evaluation",
                "Checking final outcome",
                "Reviewing the recent actions to decide whether the overall goal is complete.",
            )
            eval_screenshot = None if (is_coding or is_computer_use) else _capture_screenshot_b64(screen_width, screen_height)
            eval_res = await self._run_with_phase_updates(
                task_id,
                "Evaluating results...",
                "Still evaluating",
                provider.evaluate, goal, history, eval_screenshot, mode
            )
            status = "done" if eval_res.get("complete") else "failed"
            self._finalize(task_id, status, eval_res.get("reason", ""))
            await self._emit_reasoning(
                task_id,
                "Evaluation",
                "Final verdict ready",
                eval_res.get("reason", ""),
            )

            await self._emit(task_id, "done", {**eval_res, "finished_at": datetime.now(timezone.utc).isoformat()})
            
            # Store goal outcome in memory
            self.memory.add("task_outcome", f"Goal: {goal} | Outcome: {eval_res.get('complete')} | Reason: {eval_res.get('reason')}")
            
        except asyncio.CancelledError:
            self._finalize(task_id, "cancelled", "task cancelled")
            await self._emit_reasoning(
                task_id,
                "Stopped",
                "Task cancelled",
                "Execution stopped before the goal was finished.",
            )
            await self._emit(task_id, "cancelled", {"message": "Task cancelled", "finished_at": datetime.now(timezone.utc).isoformat()})

        except Exception as e:
            msg = str(e)
            # Surface actionable hints for common provider failures
            if "choices" in msg or "Provider returned error" in msg or "rate limit" in msg.lower():
                msg = f"{msg} — Try switching to a different model (e.g. Gemma or Llama) in the model dropdown."
            self._finalize(task_id, "failed", msg)
            _ts = datetime.now(timezone.utc).isoformat()
            await self._emit_reasoning(
                task_id,
                "Error",
                "Execution failed",
                msg,
            )
            await self._emit(task_id, "error", {"message": msg})
            await self._emit(task_id, "done", {"complete": False, "reason": msg, "finished_at": _ts})

        finally:
            self._active_tasks.pop(task_id, None)
            self._paused_tasks.discard(task_id)
            # Clean up background browser for this task
            browser = self._bg_browsers.pop(task_id, None)
            if browser:
                try:
                    await browser.stop()
                except Exception:
                    pass
            # Reset tool executor state
            self.tools._bg_browser = None
            self.tools._background_mode = True  # safe default

    def _finalize(self, task_id: str, status: str, reason: str = ""):
        if self._on_task_complete:
            self._on_task_complete(task_id, status, reason)

    async def _wait_for_approval(self, task_id: str, action_id: str) -> bool:
        fut_id = f"{task_id}:{action_id}"
        self._approvals[fut_id] = asyncio.Future()
        try:
            return await self._approvals[fut_id]
        finally:
            self._approvals.pop(fut_id, None)

    def submit_approval(self, task_id: str, action_id: str, approved: bool):
        fut_id = f"{task_id}:{action_id}"
        if fut_id in self._approvals:
            self._approvals[fut_id].set_result(approved)

    async def _wait_for_permission(self, task_id: str, action_id: str) -> bool:
        fut_id = f"{task_id}:{action_id}"
        self._permission_waits[fut_id] = asyncio.Future()
        try:
            return await self._permission_waits[fut_id]
        finally:
            self._permission_waits.pop(fut_id, None)

    def submit_permission(self, task_id: str, action_id: str, granted: bool):
        fut_id = f"{task_id}:{action_id}"
        if fut_id in self._permission_waits:
            self._permission_waits[fut_id].set_result(granted)

    def cancel_task(self, task_id: str) -> bool:
        if task_id in self._active_tasks:
            self._active_tasks[task_id].cancel()
            del self._active_tasks[task_id]
            self._paused_tasks.discard(task_id)
            # Clean up background browser if any
            browser = self._bg_browsers.pop(task_id, None)
            if browser:
                asyncio.ensure_future(browser.stop())
            return True
        return False

    async def shutdown(self):
        """Clean up all background browsers on server shutdown."""
        for browser in self._bg_browsers.values():
            try:
                await browser.stop()
            except Exception:
                pass
        self._bg_browsers.clear()

    def pause_task(self, task_id: str):
        self._paused_tasks.add(task_id)

    def resume_task(self, task_id: str):
        self._paused_tasks.discard(task_id)


def _summarize_args(action_type: str, args: dict) -> str:
    """One-line summary of action args for the activity log."""
    if action_type == "run_command":
        return (args.get("command") or "")[:80]
    if action_type == "bash":
        return (args.get("command") or "")[:80]
    if action_type == "text_editor":
        return f"{args.get('command','')} {args.get('path','')}".strip()
    if action_type == "computer":
        return args.get("action") or ""
    if action_type in ("read_file", "write_file", "move_file", "text_create",
                       "text_view", "text_str_replace", "text_insert"):
        return args.get("path") or args.get("src") or ""
    if action_type == "browser_open":
        return args.get("url") or ""
    if action_type in ("browser_click", "browser_type"):
        return args.get("selector") or ""
    if action_type == "api_call":
        return f"{args.get('method','GET')} {args.get('url','')})"[:80]
    if action_type == "web_search":
        return (args.get("query") or "")[:80]
    if action_type in ("mouse_click", "mouse_move", "double_click", "right_click"):
        return f"({args.get('x')}, {args.get('y')})"
    if action_type in ("keyboard_type", "type_with_delay"):
        text = args.get("text") or ""
        return text[:40] + ("..." if len(text) > 40 else "")
    if action_type == "key_combo":
        return args.get("keys") or ""
    return ""
