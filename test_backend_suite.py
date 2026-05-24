"""Backend smoke tests — exercises the FastAPI server the widget talks to.

Runs four scenarios that mirror real widget use:
  1. coding    — write a function
  2. debugging — find the bug in a snippet
  3. browser   — search the web and report a fact
  4. vision    — screenshot a specific window (Notepad with known text)
                 and describe its contents (the scoped-window mode)
"""
from __future__ import annotations

import os, secrets, subprocess, sys, tempfile, time, json
import httpx

# Force UTF-8 on Windows so emoji / smart-quotes don't crash the print loop.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _s(x) -> str:
    """ASCII-fold helper for the rare characters cp1252 still chokes on."""
    if x is None:
        return ""
    return str(x).encode("utf-8", "replace").decode("utf-8", "replace")

BASE = "http://127.0.0.1:8000"
TIMEOUT = 360  # per task, seconds (free OpenRouter tier can be slow)


def run_task(name: str, goal: str, *, mode: str = "auto",
             isolated_app: str | None = None,
             model: str | None = None) -> dict:
    tid = f"test-{name}-{secrets.token_hex(3)}"
    payload: dict = {"task_id": tid, "goal": goal, "mode": mode}
    if isolated_app:
        payload["isolated_app"] = isolated_app
    # Free-only: omit `model` so the server auto-picks from the :free pool
    # unless the caller explicitly passes a free model string.
    if model:
        payload["model"] = model

    print(f"\n{'=' * 70}\n[{name.upper()}] mode={mode} "
          f"model={payload.get('model', '<auto-pick free>')}"
          f"{f' isolated_app={isolated_app!r}' if isolated_app else ''}")
    print(f"goal: {goal}")
    print("=" * 70)

    with httpx.Client(timeout=30.0) as c:
        c.post(f"{BASE}/api/session")
        r = c.post(f"{BASE}/api/tasks", json=payload)
        if r.status_code >= 400:
            print(f"❌ submit failed {r.status_code}: {r.text[:300]}")
            return {"ok": False, "error": r.text}

        deadline = time.time() + TIMEOUT
        seen = 0
        last_status = ""
        final_reason = None
        outcome = None
        agent_texts: list[str] = []
        tool_calls: list[str] = []
        while time.time() < deadline:
            time.sleep(1.2)
            try:
                log = c.get(f"{BASE}/api/tasks/{tid}/log").json().get("log", [])
            except Exception:
                continue
            for ev in log[seen:]:
                t = ev.get("type")
                msg = ev.get("message") or ev.get("reason") or ""
                if t == "status" and msg and msg != last_status:
                    print(f"  . {_s(msg)[:160]}")
                    last_status = msg
                elif t == "tool":
                    nm = ev.get("name", "?")
                    tool_calls.append(nm)
                    print(f"  -> tool: {nm} {_s(ev.get('args',''))[:120]}")
                elif t == "agent":
                    txt = ev.get("text") or ""
                    if txt:
                        agent_texts.append(txt)
                        print(f"  >> {_s(txt)[:200]}")
                elif t in ("done", "complete"):
                    final_reason = msg
                    outcome = "done"
                elif t in ("error", "failed", "cancelled"):
                    final_reason = msg
                    outcome = t
            seen = len(log)
            if outcome:
                break
        elapsed = TIMEOUT - (deadline - time.time())
        print(f"\nfinal: {outcome or 'TIMEOUT'} after {elapsed:.0f}s")
        if final_reason:
            print(f"reason: {_s(final_reason)[:600]}")
        # Pull the full record so we see what was returned to the user
        try:
            rec = c.get(f"{BASE}/api/tasks/{tid}").json()
            final_text = rec.get("final_message") or rec.get("reason") or ""
            if final_text:
                print(f"\n--- agent reply ({len(final_text)} chars) ---")
                print(_s(final_text)[:1500])
        except Exception:
            pass
        return {"ok": outcome == "done", "outcome": outcome,
                "reason": final_reason, "elapsed": elapsed,
                "tools": tool_calls, "texts": agent_texts}


def launch_notepad_with_text(text: str) -> int | None:
    """Open Notepad with `text` pre-loaded. Returns the PID or None."""
    tmp = os.path.join(tempfile.gettempdir(),
                       f"capsule_vision_{secrets.token_hex(3)}.txt")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    p = subprocess.Popen(["notepad.exe", tmp])
    time.sleep(2.5)  # let the window open
    return p.pid


def main():
    only = set(sys.argv[1:])  # e.g. `python test_backend_suite.py vision`
    results = {}

    def maybe(name: str, fn):
        if only and name not in only:
            return
        results[name] = fn()

    # 1. Coding
    maybe("coding", lambda: run_task(
        "coding",
        "Write a Python function `fib(n)` that returns the nth Fibonacci number "
        "(0-indexed, so fib(0)=0, fib(1)=1). Show the code in your reply.",
        mode="coding",
    ))

    # 2. Debugging
    maybe("debugging", lambda: run_task(
        "debugging",
        "There's a bug in this Python function — find it and explain the fix in one sentence:\n"
        "```python\n"
        "def average(nums):\n"
        "    total = 0\n"
        "    for n in nums:\n"
        "        total = n\n"
        "    return total / len(nums)\n"
        "```",
        mode="coding",
    ))

    # 3. Browser
    maybe("browser", lambda: run_task(
        "browser",
        "Search the web for the current population of Tokyo and report the number "
        "with the source URL.",
        mode="auto",
    ))

    # 4. Vision (scoped window) — needs a multimodal free model
    pid = None
    if not only or "vision" in only:
        notepad_text = (
            "LIQUID_GLASS_TEST_TOKEN\n"
            "The capital of France is Paris.\n"
            "Pi to four decimals is 3.1416.\n"
        )
        pid = launch_notepad_with_text(notepad_text)
        print(f"\n[setup] launched Notepad pid={pid} with sentinel "
              f"'LIQUID_GLASS_TEST_TOKEN'")
        maybe("vision", lambda: run_task(
            "vision",
            "You are scoped to a specific Notepad window. FIRST: call the "
            "`screenshot` tool to capture that window's pixels. THEN: look at "
            "the screenshot and quote back EVERY line of text visible in it, "
            "verbatim. Do not use bash, dir, or file-reading tools — only "
            "read what's in the image. The first line is a sentinel token "
            "starting with LIQUID_GLASS_.",
            mode="computer_isolated",
            isolated_app="Notepad",
            model="openrouter/google/gemma-4-31b-it:free",
        ))

    # Cleanup
    if pid:
        try:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        except Exception:
            pass

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for name, r in results.items():
        ok = "PASS" if r["ok"] else "FAIL"
        out = r.get("outcome") or "TIMEOUT"
        elapsed = r.get("elapsed") or 0
        print(f"[{ok}] {name:10s} {out:10s} {elapsed:.0f}s")
    failed = sum(1 for r in results.values() if not r["ok"])
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
