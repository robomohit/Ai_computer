"""Live end-to-end smoke: run the same task twice against the real server.

Run 1 should plan live and COMPILE a trace on success.
Run 2 should REPLAY the trace (status message proves it) and finish with a
single model call. Exercises providers, agent loop, trace store, SSE log.
"""
from __future__ import annotations

import json
import sys
import time
import uuid

import httpx

BASE = "http://127.0.0.1:8000"
GOAL = "create a file named smoke_test.txt containing exactly: hi orynn — then read it back to verify its contents and finish"


def run_task(client: httpx.Client, label: str) -> dict:
    task_id = f"smoke-{label}-{uuid.uuid4().hex[:8]}"
    r = client.post(f"{BASE}/api/tasks", json={
        "task_id": task_id, "goal": GOAL, "mode": "coding",
    })
    print(f"[{label}] create: {r.status_code} {r.text[:200] if r.status_code >= 400 else ''}")
    r.raise_for_status()

    deadline = time.time() + 150
    status = "?"
    while time.time() < deadline:
        time.sleep(2)
        t = client.get(f"{BASE}/api/tasks/{task_id}").json()
        status = t.get("status", "?")
        if status in ("done", "failed", "cancelled", "complete"):
            break
    log = client.get(f"{BASE}/api/tasks/{task_id}/log").json()
    events = log if isinstance(log, list) else log.get("events", log.get("log", []))
    statuses, actions = [], []
    for ev in events if isinstance(events, list) else []:
        data = ev.get("data", ev) if isinstance(ev, dict) else {}
        etype = ev.get("type", "") if isinstance(ev, dict) else ""
        if etype == "status" and isinstance(data, dict):
            statuses.append(str(data.get("message", "")))
        if etype == "action_result" and isinstance(data, dict):
            actions.append(f"{data.get('action_type')}:{'ok' if data.get('ok') else 'FAIL'}")
    return {"task_id": task_id, "status": status, "statuses": statuses, "actions": actions}


def main() -> int:
    with httpx.Client(timeout=30) as client:
        client.post(f"{BASE}/api/session")

        one = run_task(client, "run1")
        print(f"[run1] final: {one['status']}")
        print(f"[run1] actions: {one['actions']}")
        compiled = any("Compiled this run" in s for s in one["statuses"])
        print(f"[run1] compiled trace: {compiled}")

        if one["status"] != "done":
            print("[run1] did not finish clean — replay check skipped")
            for s in one["statuses"][-8:]:
                print("   status:", s[:120])
            return 1

        two = run_task(client, "run2")
        print(f"[run2] final: {two['status']}")
        print(f"[run2] actions: {two['actions']}")
        replayed = any("Replaying a previously successful run" in s for s in two["statuses"])
        print(f"[run2] replayed trace: {replayed}")
        print("PASS" if (compiled and replayed and two["status"] == "done") else "PARTIAL")
        return 0


if __name__ == "__main__":
    sys.exit(main())
