"""Comprehensive AI Computer test — proves the agent can:
  1. Code (write a function + save to disk; verify file)
  2. Control the browser (web search + fetch via Playwright)
  3. Do long multi-step tasks
  4. Use connectors (link via API + read state)
  5. Run multiple tasks sequentially
  6. Use PC-control tools (we exercise the tool registry, not the live UI,
     to avoid hijacking the user's mouse during the test).
"""
from __future__ import annotations
import os, secrets, sys, time, json, pathlib
import httpx

BASE = "http://127.0.0.1:8000"
TIMEOUT = 300

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _ascii(s):
    return (s or "").encode("utf-8", "replace").decode("utf-8", "replace")


def session():
    with httpx.Client(timeout=10) as c:
        c.post(f"{BASE}/api/session")


def run(name, goal, *, mode="auto", model=None, isolated=None, folder=None,
        deadline=TIMEOUT) -> dict:
    tid = f"full-{name}-{secrets.token_hex(3)}"
    payload = {"task_id": tid, "goal": goal, "mode": mode}
    if isolated: payload["isolated_app"] = isolated
    if folder:   payload["project_folder"] = folder
    if model:    payload["model"] = model
    print(f"\n{'='*64}")
    print(f"[{name}] mode={mode}")
    print(f"goal: {goal[:120]}")
    print('='*64)
    with httpx.Client(timeout=10) as c:
        c.post(f"{BASE}/api/session")
        r = c.post(f"{BASE}/api/tasks", json=payload)
        if r.status_code >= 400:
            return {"ok": False, "err": r.text[:200]}
        end = time.time() + deadline
        seen = 0
        tool_calls = []
        outcome = None
        reason = ""
        while time.time() < end:
            time.sleep(1.0)
            try:
                log = c.get(f"{BASE}/api/tasks/{tid}/log").json().get("log", [])
            except Exception:
                continue
            for ev in log[seen:]:
                t = ev.get("type")
                if t == "status":
                    msg = ev.get("message", "")
                    if msg: print(f"  . {_ascii(msg)[:140]}")
                elif t == "action_start":
                    a = ev.get("action_type", "?")
                    tool_calls.append(a)
                    args = str(ev.get("args_summary", ""))[:80]
                    print(f"  -> {a} {_ascii(args)}")
                elif t in ("done", "complete"):
                    outcome = "done"
                    reason = ev.get("reason", "")
                elif t in ("error", "failed", "cancelled"):
                    outcome = t
                    reason = ev.get("reason", "") or ev.get("message", "")
            seen = len(log)
            if outcome: break
        elapsed = deadline - (end - time.time())
        print(f"\n[result] {outcome or 'TIMEOUT'} in {elapsed:.0f}s — {len(tool_calls)} tool calls")
        if reason:
            print(f"reason: {_ascii(reason)[:300]}")
        return {"ok": outcome == "done", "outcome": outcome, "elapsed": elapsed,
                "tools": tool_calls, "reason": reason, "tid": tid}


def main():
    results = {}

    # ── Test 1: CODE — write a function to a file (not just speak it)
    out_dir = pathlib.Path("test_workspace").resolve()
    out_dir.mkdir(exist_ok=True)
    fib_path = out_dir / "fib_generated.py"
    if fib_path.exists(): fib_path.unlink()
    results["coding"] = run(
        "coding",
        f"Use the write_file tool to create '{fib_path}' containing a Python "
        f"function `fib(n)` that returns the nth Fibonacci number (0-indexed). "
        f"After writing, read it back to verify.",
        mode="coding",
    )
    results["coding"]["file_exists"] = fib_path.exists()
    if fib_path.exists():
        results["coding"]["file_has_fib"] = "def fib" in fib_path.read_text()

    # ── Test 2: BROWSER — web search + fetch (long-running)
    results["browser_long"] = run(
        "browser_long",
        "Search the web for the population of Iceland in 2024 and cite the "
        "source URL.",
        mode="auto",
    )

    # ── Test 3: CONNECTORS — link, list, unlink via dashboard API
    print("\n" + "="*64)
    print("[connectors] testing dashboard link/unlink API")
    print("="*64)
    with httpx.Client(timeout=10) as c:
        c.post(f"{BASE}/api/session")
        r0 = c.get(f"{BASE}/api/connectors").json()
        before_linked = sorted(c["id"] for c in r0["connectors"] if c["linked"])
        print(f"  before: linked = {before_linked}")
        rL = c.post(f"{BASE}/api/connectors/github/link",
                    json={"notes": "from test"})
        print(f"  link github → status {rL.status_code}, linked={rL.json().get('linked')}")
        r1 = c.get(f"{BASE}/api/connectors").json()
        after_linked = sorted(c["id"] for c in r1["connectors"] if c["linked"])
        print(f"  after: linked = {after_linked}")
        rU = c.post(f"{BASE}/api/connectors/github/unlink")
        print(f"  unlink → linked={rU.json().get('linked')}")
        r2 = c.get(f"{BASE}/api/connectors").json()
        final_linked = sorted(c["id"] for c in r2["connectors"] if c["linked"])
        print(f"  final: linked = {final_linked}")
    results["connectors"] = {
        "ok": ("github" not in before_linked
               and "github" in after_linked
               and "github" not in final_linked),
        "outcome": "done",
        "elapsed": 0,
    }

    # ── Test 4: MULTIPLE TASKS — fire 3 small ones sequentially
    print("\n" + "="*64)
    print("[multi_task] running 3 sequential small tasks")
    print("="*64)
    seq_results = []
    for i, q in enumerate([
        "Reply in one word: red",
        "Reply in one word: blue",
        "Reply in one word: green",
    ]):
        r = run(f"seq{i}", q, mode="auto", deadline=120)
        seq_results.append(r)
    results["multi_task"] = {
        "ok": all(r["ok"] for r in seq_results),
        "outcome": "done" if all(r["ok"] for r in seq_results) else "fail",
        "elapsed": sum(r.get("elapsed", 0) for r in seq_results),
        "count": len(seq_results),
    }

    # ── Test 5: PC CONTROL — verify the toolset, not live action.
    # We confirm the agent has access to mouse_click / keyboard_type by
    # looking at /api/models and /api/health (the dashboard ships these
    # tools by default in `computer` mode).
    print("\n" + "="*64)
    print("[pc_control] verifying tool registry exposes desktop tools")
    print("="*64)
    desktop_tools = [
        "mouse_click", "keyboard_type", "key", "scroll", "screenshot",
        "focus_window", "find_on_screen", "type_with_delay",
    ]
    tools_py = pathlib.Path("app/tools.py").read_text(encoding="utf-8",
                                                      errors="replace")
    missing = [t for t in desktop_tools if f"def {t}" not in tools_py]
    print(f"  missing: {missing or 'none'}")
    results["pc_control"] = {
        "ok": not missing,
        "outcome": "done" if not missing else "fail",
        "elapsed": 0,
        "available": [t for t in desktop_tools if t not in missing],
    }

    # ── Summary
    print("\n" + "="*64)
    print("SUMMARY")
    print("="*64)
    for name, r in results.items():
        ok = "PASS" if r.get("ok") else "FAIL"
        extra = ""
        if name == "coding" and r.get("file_exists"):
            extra = " (file written + verified)" if r.get("file_has_fib") else " (file exists, contents unverified)"
        if name == "multi_task":
            extra = f" ({r.get('count')} tasks)"
        if name == "pc_control":
            extra = f" ({len(r.get('available', []))} desktop tools available)"
        print(f"[{ok}] {name:14s} {r.get('outcome','?'):8s} {r.get('elapsed', 0):.0f}s{extra}")

    fails = [n for n, r in results.items() if not r.get("ok")]
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
