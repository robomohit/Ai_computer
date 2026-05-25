"""Desktop control health check — verifies free-tier model actually CALLS
the right tools when given a desktop task, and that our virtual cursor
overlay wiring works end-to-end.

Two parts:
  1. Send a `computer`-mode task that should at minimum produce a
     `screenshot` action_start (hardening prompt forces "screenshot first").
  2. Manually exercise the virtual cursor overlay to confirm it renders
     without crashing.
"""
from __future__ import annotations
import os, secrets, sys, time
import httpx

BASE = "http://127.0.0.1:8000"


def session():
    with httpx.Client(timeout=10) as c:
        c.post(f"{BASE}/api/session")


def run_desktop(name: str, goal: str, deadline: int = 240) -> dict:
    tid = f"dt-{name}-{secrets.token_hex(3)}"
    print(f"\n=== {name} ===")
    print(f"goal: {goal[:120]}")
    with httpx.Client(timeout=15) as c:
        c.post(f"{BASE}/api/session")
        r = c.post(f"{BASE}/api/tasks", json={
            "task_id": tid,
            "goal": goal,
            "mode": "computer",
        })
        if r.status_code >= 400:
            print(f"submit failed: {r.text[:200]}")
            return {"ok": False}
        deadline_t = time.time() + deadline
        seen = 0
        tools = []
        outcome = None
        reason = ""
        while time.time() < deadline_t:
            time.sleep(1.0)
            try:
                log = c.get(f"{BASE}/api/tasks/{tid}/log").json().get("log", [])
            except Exception:
                continue
            for ev in log[seen:]:
                t = ev.get("type")
                if t == "action_start":
                    a = ev.get("action_type", "?")
                    tools.append(a)
                    print(f"  -> {a} {str(ev.get('args_summary',''))[:60]}")
                elif t in ("done", "complete"):
                    outcome = "done"
                    reason = ev.get("reason", "")
                elif t in ("error", "failed", "cancelled"):
                    outcome = t
                    reason = ev.get("reason", "") or ev.get("message", "")
            seen = len(log)
            if outcome:
                break
        print(f"[{outcome or 'TIMEOUT'}] tools={tools[:8]}")
        return {
            "ok": outcome == "done",
            "outcome": outcome,
            "tools": tools,
            "called_screenshot": "screenshot" in tools,
        }


def test_cursor_overlay() -> bool:
    """Construct + animate the overlay headlessly. Pass if no exception."""
    print("\n=== cursor_overlay ===")
    try:
        # Run in a subprocess so it doesn't conflict with the running app
        import subprocess
        r = subprocess.run(
            [sys.executable, "test_cursor.py"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True, timeout=15, text=True
        )
        ok = r.returncode == 0
        print(f"  [{'PASS' if ok else 'FAIL'}] exit={r.returncode}")
        if r.stderr:
            print(f"  stderr: {r.stderr[:200]}")
        return ok
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    results = {}

    # Test 1: A safe computer-mode task that should at minimum screenshot
    # the screen. We don't ask it to click anything destructive — just
    # describe what's visible. That exercises the screenshot pipeline.
    results["screenshot_pipeline"] = run_desktop(
        "screenshot_pipeline",
        "Take a screenshot of the desktop and briefly describe what's "
        "visible in the top-left quadrant. Use the screenshot tool. "
        "Don't click anything. Reply in one sentence."
    )

    # Test 2: Cursor overlay renders without crashing
    cursor_ok = test_cursor_overlay()
    results["cursor_overlay"] = {"ok": cursor_ok, "outcome": "done" if cursor_ok else "fail"}

    # Summary
    print("\n" + "=" * 56)
    print("DESKTOP CONTROL SUMMARY")
    print("=" * 56)
    for name, r in results.items():
        ok = "PASS" if r.get("ok") else "FAIL"
        extra = ""
        if "called_screenshot" in r:
            extra = f" (screenshot called: {r['called_screenshot']})"
        print(f"[{ok}] {name:24s} {r.get('outcome', '?'):8s}{extra}")

    sys.exit(1 if any(not r.get("ok") for r in results.values()) else 0)


if __name__ == "__main__":
    main()
