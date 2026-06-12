"""Harness benchmark — makes "best AI harness for free models" a NUMBER.

Drives a small suite of goals through the real server, each goal twice,
and scores the run from the persisted event log (no agent instrumentation
needed — every metric is derived from events the agent already emits):

  model_calls   "Thinking through step N…" statuses (one per model round-trip)
  ttft          gap between "Thinking through step N" and "Working on step N"
  race wins     provider_info events with race_winner
  compiled      run 1 ends with "Compiled this run"
  replayed      run 2 starts with "Replaying a previously successful run"
  wall time     last event ts − first event ts

Usage:  python scripts/bench.py            (server must be running on :8000)
        python scripts/bench.py --json     (also write bench_results.json)
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import datetime

import httpx

BASE = "http://127.0.0.1:8000"
TIMEOUT_S = 180

# Two-action+ goals so successful runs COMPILE (the _MIN_ACTIONS=2 floor).
GOALS = [
    ("two_files", "create a file named bench_a.txt containing exactly: alpha "
                  "— then create bench_b.txt containing exactly: beta, then finish"),
    ("write_verify", "create a file named bench_c.txt containing exactly: gamma "
                     "— then read it back to verify its contents and finish"),
]


def _parse_ts(ts: str) -> float:
    try:
        return datetime.fromisoformat(ts).timestamp()
    except Exception:
        return 0.0


def run_task(client: httpx.Client, goal: str, label: str) -> dict:
    task_id = f"bench-{label}-{uuid.uuid4().hex[:8]}"
    r = client.post(f"{BASE}/api/tasks", json={"task_id": task_id, "goal": goal, "mode": "coding"})
    r.raise_for_status()
    deadline = time.time() + TIMEOUT_S
    status = "?"
    while time.time() < deadline:
        time.sleep(2)
        status = client.get(f"{BASE}/api/tasks/{task_id}").json().get("status", "?")
        if status in ("done", "failed", "cancelled", "complete"):
            break
    log = client.get(f"{BASE}/api/tasks/{task_id}/log").json()
    events = log if isinstance(log, list) else log.get("events", log.get("log", []))
    return score_events(task_id, status, events if isinstance(events, list) else [])


def score_events(task_id: str, status: str, events: list) -> dict:
    model_calls = 0
    ttfts: list[float] = []
    race_wins: dict[str, int] = {}
    compiled = replayed = False
    pending_think_ts: float | None = None
    first_ts = last_ts = None

    for ev in events:
        if not isinstance(ev, dict):
            continue
        ts = _parse_ts(str(ev.get("ts", "")))
        if ts:
            first_ts = ts if first_ts is None else first_ts
            last_ts = ts
        msg = str(ev.get("message", ""))
        if ev.get("type") == "status" and not ev.get("heartbeat"):
            if msg.startswith("Thinking through step"):
                model_calls += 1
                pending_think_ts = ts
            elif msg.startswith("Working on step") and pending_think_ts:
                ttfts.append(ts - pending_think_ts)
                pending_think_ts = None
            elif "Compiled this run" in msg:
                compiled = True
            elif "Replaying a previously successful run" in msg:
                replayed = True
        winner = ev.get("race_winner")
        if winner:
            race_wins[winner] = race_wins.get(winner, 0) + 1

    return {
        "task_id": task_id,
        "status": status,
        "model_calls": model_calls,
        "ttft_avg_s": round(sum(ttfts) / len(ttfts), 2) if ttfts else None,
        "race_wins": race_wins,
        "compiled": compiled,
        "replayed": replayed,
        "wall_s": round(last_ts - first_ts, 1) if first_ts and last_ts else None,
    }


def main() -> int:
    results = []
    with httpx.Client(timeout=30) as client:
        client.post(f"{BASE}/api/session")
        for name, goal in GOALS:
            one = run_task(client, goal, f"{name}-r1")
            two = run_task(client, goal, f"{name}-r2")
            results.append({"goal": name, "run1": one, "run2": two})

    print(f"\n{'goal':<14}{'run':<5}{'status':<9}{'calls':<7}{'ttft':<7}{'wall':<7}{'flags'}")
    print("-" * 62)
    ok = True
    for r in results:
        for run_label, run in (("r1", r["run1"]), ("r2", r["run2"])):
            flags = []
            if run["compiled"]:
                flags.append("compiled")
            if run["replayed"]:
                flags.append("REPLAY")
            if run["race_wins"]:
                flags.append("race:" + ",".join(f"{k}x{v}" for k, v in run["race_wins"].items()))
            print(f"{r['goal']:<14}{run_label:<5}{run['status']:<9}"
                  f"{run['model_calls']:<7}{str(run['ttft_avg_s']):<7}"
                  f"{str(run['wall_s']):<7}{' '.join(flags)}")
        r1, r2 = r["run1"], r["run2"]
        if r1["status"] == "done" and r2["status"] == "done" and r2["replayed"]:
            saved = r1["model_calls"] - r2["model_calls"]
            print(f"{'':14}=> replay saved {saved} model call(s) "
                  f"({r1['model_calls']} -> {r2['model_calls']})")
        else:
            ok = False

    if "--json" in sys.argv:
        with open("bench_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print("\nwrote bench_results.json")
    print("\nBENCH " + ("PASS" if ok else "PARTIAL — see flags above"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
