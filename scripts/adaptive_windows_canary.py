from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.tools import ToolExecutor  # noqa: E402


def _tool_step(name: str, fn: Callable[[], Any]) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        res = fn()
        ok = bool(getattr(res, "ok", False))
        data = getattr(res, "data", None) or {}
        return {
            "name": name,
            "ok": ok,
            "duration_s": round(time.perf_counter() - started, 3),
            "output": str(getattr(res, "output", ""))[:1200],
            "data": data,
            "control_layer": (data.get("overlay") or {}).get("control_layer", ""),
        }
    except Exception as exc:
        return {
            "name": name,
            "ok": False,
            "duration_s": round(time.perf_counter() - started, 3),
            "error": str(exc),
        }


def _window_probe_step(name: str, fn: Callable[[], Any]) -> dict[str, Any]:
    """Run a window-targeting tool without serializing app titles/control names."""
    started = time.perf_counter()
    try:
        res = fn()
        data = getattr(res, "data", None) or {}
        return {
            "name": name,
            "ok": bool(getattr(res, "ok", False)),
            "duration_s": round(time.perf_counter() - started, 3),
            "output": "window ready" if getattr(res, "ok", False) else str(getattr(res, "output", ""))[:240],
            "data": {
                "hwnd_present": bool(data.get("hwnd")),
                "pid_present": bool(data.get("pid")),
                "title_present": bool(data.get("title")),
            },
        }
    except Exception as exc:
        return {
            "name": name,
            "ok": False,
            "duration_s": round(time.perf_counter() - started, 3),
            "error": str(exc),
        }


def _adaptive_map_step(name: str, fn: Callable[[], Any]) -> dict[str, Any]:
    """Summarize an adaptive map without dumping private control labels."""
    started = time.perf_counter()
    try:
        res = fn()
        data = getattr(res, "data", None) or {}
        graph = data.get("graph") or {}
        groups = graph.get("groups") or {}
        adaptive = data.get("adaptive") or {}
        overlay = data.get("overlay") or {}
        return {
            "name": name,
            "ok": bool(getattr(res, "ok", False)),
            "duration_s": round(time.perf_counter() - started, 3),
            "output": (
                f"mapped {int(graph.get('named_control_count') or 0)} named controls"
                if getattr(res, "ok", False)
                else str(getattr(res, "output", ""))[:240]
            ),
            "data": {
                "graph": {
                    "app": graph.get("app"),
                    "control_count": int(graph.get("control_count") or 0),
                    "named_control_count": int(graph.get("named_control_count") or 0),
                    "group_counts": {k: len(v or []) for k, v in groups.items()},
                },
                "recovered_by": data.get("recovered_by", ""),
                "recovery_attempts": data.get("recovery_attempts", []),
                "adaptive_failure_class": adaptive.get("failure_class", ""),
                "adaptive_resolvers": [r.get("id") for r in adaptive.get("resolvers") or []],
                "overlay": {
                    "control_layer": overlay.get("control_layer", ""),
                },
            },
            "control_layer": overlay.get("control_layer", ""),
        }
    except Exception as exc:
        return {
            "name": name,
            "ok": False,
            "duration_s": round(time.perf_counter() - started, 3),
            "error": str(exc),
        }


def _find_summary_step(name: str, fn: Callable[[], Any]) -> dict[str, Any]:
    """Summarize a selector probe without returning matched labels."""
    started = time.perf_counter()
    try:
        res = fn()
        data = getattr(res, "data", None) or {}
        items = data.get("items") or []
        top = items[0] if items else {}
        overlay = data.get("overlay") or {}
        adaptive = data.get("adaptive") or {}
        return {
            "name": name,
            "ok": bool(getattr(res, "ok", False)),
            "duration_s": round(time.perf_counter() - started, 3),
            "output": f"{len(items)} match(es)" if getattr(res, "ok", False) else str(getattr(res, "output", ""))[:240],
            "data": {
                "item_count": len(items),
                "top_name_present": bool(top.get("name")),
                "top_control_type": top.get("control_type", ""),
                "top_score": top.get("score"),
                "top_has_rect": bool((top.get("width") or 0) and (top.get("height") or 0)),
                "adaptive_failure_class": adaptive.get("failure_class", ""),
                "overlay": {
                    "control_layer": overlay.get("control_layer", ""),
                    "fallback_reason": overlay.get("fallback_reason", ""),
                },
            },
            "control_layer": overlay.get("control_layer", ""),
        }
    except Exception as exc:
        return {
            "name": name,
            "ok": False,
            "duration_s": round(time.perf_counter() - started, 3),
            "error": str(exc),
        }


def _kill_started_process(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=3)
    except Exception:
        try:
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/F"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except Exception:
            pass


def _foreground_hotkey(tools: ToolExecutor, keys: str):
    tools.set_isolated_hwnd(None, None)
    return tools.key(keys)


def _discard_notepad_tab(tools: ToolExecutor, title_hint: str) -> None:
    try:
        tools.focus_window(title_hint)
        _foreground_hotkey(tools, "ctrl+w")
        time.sleep(0.25)
        dont_save = tools.uia_find("Don't Save", title_hint)
        if dont_save.ok:
            tools.uia_click("Don't Save", title_hint)
    except Exception:
        pass


def _canary_result(name: str, started: float, steps: list[dict[str, Any]]) -> dict[str, Any]:
    failed = [step for step in steps if not step.get("ok")]
    layers = [step.get("control_layer") for step in steps if step.get("control_layer")]
    graph_steps = [
        step for step in steps
        if isinstance(step.get("data"), dict) and step["data"].get("graph")
    ]
    return {
        "name": name,
        "ok": not failed,
        "duration_s": round(time.perf_counter() - started, 3),
        "steps": steps,
        "failed_steps": [step["name"] for step in failed],
        "control_layers": layers,
        "affordance_maps": len(graph_steps),
    }


def run_notepad_canary(workspace: Path) -> dict[str, Any]:
    started = time.perf_counter()
    steps: list[dict[str, Any]] = []
    proc: subprocess.Popen | None = None
    tools = ToolExecutor(workspace)
    text = f"Orynn adaptive canary {int(time.time())}"
    canary_file = workspace / f"orynn-adaptive-canary-{int(time.time() * 1000)}.txt"
    canary_file.write_text("", encoding="utf-8")
    title_hint = canary_file.name
    try:
        proc = subprocess.Popen(["notepad.exe", str(canary_file)])
        steps.append(_tool_step(
            "wait_for_notepad",
            lambda: tools.wait_for_window(title_hint, timeout=10.0, paint_seconds=0.2),
        ))
        steps.append(_tool_step(
            "map_notepad",
            lambda: tools.adaptive_observe(title_hint, cap=120),
        ))
        steps.append(_tool_step(
            "type_text",
            lambda: tools.uia_type("Text editor", text, title_hint, clear_first=True),
        ))
        steps.append(_tool_step(
            "read_editor",
            lambda: tools.uia_find("Text editor", title_hint),
        ))
    finally:
        _discard_notepad_tab(tools, title_hint)
        _kill_started_process(proc)
        try:
            canary_file.unlink(missing_ok=True)
        except Exception:
            pass
    result = _canary_result("notepad", started, steps)
    typed = next((step for step in steps if step["name"] == "type_text"), {})
    if typed.get("ok") and typed.get("data", {}).get("verified") is not True:
        result["ok"] = False
        if "type_text_unverified" not in result["failed_steps"]:
            result["failed_steps"].append("type_text_unverified")
    return result


def run_calculator_canary(workspace: Path) -> dict[str, Any]:
    started = time.perf_counter()
    steps: list[dict[str, Any]] = []
    proc: subprocess.Popen | None = None
    tools = ToolExecutor(workspace)
    try:
        proc = subprocess.Popen(["calc.exe"])
        steps.append(_tool_step(
            "wait_for_calculator",
            lambda: tools.wait_for_window("Calculator", timeout=10.0, paint_seconds=0.4),
        ))
        steps.append(_tool_step(
            "map_calculator",
            lambda: tools.adaptive_observe("Calculator", cap=160),
        ))
        steps.append(_tool_step(
            "compute_2_plus_3",
            lambda: tools.uia_click_sequence(
                ["Two", "Plus", "Three", "Equals"],
                "Calculator",
                read_result="Display",
            ),
        ))
    finally:
        _kill_started_process(proc)
        try:
            tools.force_close_window(title="Calculator", force=True)
        except Exception:
            pass
    result = _canary_result("calculator", started, steps)
    compute = next((step for step in steps if step["name"] == "compute_2_plus_3"), {})
    observed = str((compute.get("data") or {}).get("result") or compute.get("output") or "")
    if compute.get("ok") and "5" not in observed:
        result["ok"] = False
        result["failed_steps"].append("calculator_result_not_verified")
    return result


def _running_process_exe(process_name: str) -> str:
    try:
        import psutil
    except Exception:
        return ""
    wanted = process_name.lower()
    for proc in psutil.process_iter(["name", "exe"]):
        try:
            if (proc.info.get("name") or "").lower() == wanted:
                exe = proc.info.get("exe") or ""
                if exe:
                    return exe
        except Exception:
            pass
    return ""


def run_settings_canary(workspace: Path) -> dict[str, Any]:
    started = time.perf_counter()
    steps: list[dict[str, Any]] = []
    tools = ToolExecutor(workspace)
    try:
        subprocess.Popen(["explorer.exe", "ms-settings:"], close_fds=True)
        time.sleep(0.8)
    except Exception as exc:
        steps.append({
            "name": "open_settings",
            "ok": False,
            "duration_s": 0,
            "error": str(exc),
        })
    steps.append(_window_probe_step(
        "wait_for_settings",
        lambda: tools.wait_for_window("Settings", timeout=8.0, paint_seconds=0.3),
    ))
    steps.append(_adaptive_map_step(
        "map_settings",
        lambda: tools.adaptive_observe("Settings", cap=240),
    ))
    steps.append(_find_summary_step(
        "find_settings_search",
        lambda: tools.uia_find("Search box", "Settings", limit=5),
    ))
    result = _canary_result("settings", started, steps)
    mapped = next((step for step in steps if step["name"] == "map_settings"), {})
    graph = ((mapped.get("data") or {}).get("graph") or {})
    if mapped.get("ok") and int(graph.get("named_control_count") or 0) < 8:
        result["ok"] = False
        result["failed_steps"].append("settings_map_too_sparse")
    return result


def run_discord_canary(workspace: Path) -> dict[str, Any]:
    started = time.perf_counter()
    steps: list[dict[str, Any]] = []
    tools = ToolExecutor(workspace)
    exe = _running_process_exe("Discord.exe")
    if exe:
        steps.append({
            "name": "locate_discord_process",
            "ok": True,
            "duration_s": 0,
            "data": {"exe_basename": Path(exe).name},
        })
        steps.append(_tool_step("electron_check", lambda: tools.electron_check(exe)))
        try:
            subprocess.Popen([exe], close_fds=True)
            time.sleep(2.0)
            steps.append({"name": "surface_discord_window", "ok": True, "duration_s": 2.0})
        except Exception as exc:
            steps.append({
                "name": "surface_discord_window",
                "ok": False,
                "duration_s": 0,
                "error": str(exc),
            })
    else:
        steps.append({
            "name": "locate_discord_process",
            "ok": True,
            "duration_s": 0,
            "output": "process path not resolved; probing visible window",
            "data": {"exe_basename": "", "found_process": False},
        })

    steps.append(_window_probe_step(
        "wait_for_discord",
        lambda: tools.wait_for_window("Discord", timeout=8.0, paint_seconds=0.3),
    ))
    steps.append(_adaptive_map_step(
        "map_discord",
        lambda: tools.adaptive_observe("Discord", cap=240),
    ))
    steps.append(_find_summary_step(
        "find_discord_search",
        lambda: tools.uia_find("Search", "Discord", limit=5),
    ))
    result = _canary_result("discord", started, steps)
    mapped = next((step for step in steps if step["name"] == "map_discord"), {})
    graph = ((mapped.get("data") or {}).get("graph") or {})
    if mapped.get("ok") and int(graph.get("named_control_count") or 0) < 8:
        result["ok"] = False
        result["failed_steps"].append("discord_map_too_sparse")
    return result


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    failed = [result for result in results if not result.get("ok")]
    return {
        "ok": not failed,
        "total": len(results),
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "failed_canaries": [result.get("name") for result in failed],
        "duration_s": round(sum(float(result.get("duration_s") or 0) for result in results), 3),
    }


def run_canaries(names: list[str], workspace: Path) -> dict[str, Any]:
    runners = {
        "notepad": run_notepad_canary,
        "calculator": run_calculator_canary,
        "settings": run_settings_canary,
        "discord": run_discord_canary,
    }
    old_workspace = os.environ.get("ORYNN_WORKSPACE")
    os.environ["ORYNN_WORKSPACE"] = str(workspace)
    try:
        results = []
        for name in names:
            runner = runners.get(name)
            if runner is None:
                results.append({
                    "name": name,
                    "ok": False,
                    "duration_s": 0,
                    "steps": [],
                    "failed_steps": ["unknown_canary"],
                    "control_layers": [],
                    "affordance_maps": 0,
                })
                continue
            results.append(runner(workspace))
        return {
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "summary": summarize_results(results),
            "results": results,
        }
    finally:
        if old_workspace is None:
            os.environ.pop("ORYNN_WORKSPACE", None)
        else:
            os.environ["ORYNN_WORKSPACE"] = old_workspace


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local no-model Windows control canaries.")
    parser.add_argument(
        "--canary",
        action="append",
        choices=["notepad", "calculator", "settings", "discord"],
        help="Canary to run. Repeatable. Defaults to notepad.",
    )
    parser.add_argument("--workspace", default="", help="State/workspace directory for ToolExecutor.")
    parser.add_argument("--out", default="", help="Optional JSON output path.")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve() if args.workspace else Path(tempfile.mkdtemp(prefix="orynn-canary-"))
    workspace.mkdir(parents=True, exist_ok=True)
    report = run_canaries(args.canary or ["notepad"], workspace)
    text = json.dumps(report, indent=2)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["summary"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
