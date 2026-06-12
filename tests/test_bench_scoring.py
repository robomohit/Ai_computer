"""The bench scorer derives every metric from the event log alone."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from bench import score_events  # noqa: E402


def _ev(ts, etype="status", **kw):
    return {"ts": f"2026-06-11T10:00:{ts:02d}+00:00", "type": etype, **kw}


def test_score_events_full_run():
    events = [
        _ev(0, message="Thinking through step 1…"),
        _ev(2, message="Thinking… waiting on model (step 1, 2s)", heartbeat=True),
        _ev(4, message="Working on step 1…"),
        _ev(5, etype="provider_info", race_winner="openrouter",
            message="⚡ openrouter answered first"),
        _ev(6, message="Thinking through step 2…"),
        _ev(8, message="Working on step 2…"),
        _ev(20, message="⚡ Compiled this run (2 steps) — next time it replays instantly."),
    ]
    s = score_events("t1", "done", events)
    assert s["model_calls"] == 2          # heartbeats don't count
    assert s["ttft_avg_s"] == 3.0          # (4 + 2) / 2
    assert s["race_wins"] == {"openrouter": 1}
    assert s["compiled"] and not s["replayed"]
    assert s["wall_s"] == 20.0


def test_score_events_replay_run():
    events = [
        _ev(0, message="⚡ Replaying a previously successful run (2 compiled steps, "
                       "zero model calls) — verifying as it goes."),
        _ev(3, message="Thinking through step 3…"),
        _ev(5, message="Working on step 3…"),
    ]
    s = score_events("t2", "done", events)
    assert s["replayed"] and not s["compiled"]
    assert s["model_calls"] == 1           # only the final verify turn


def test_score_events_empty_and_garbage():
    s = score_events("t3", "failed", [None, "junk", {"no_ts": True}])
    assert s["status"] == "failed"
    assert s["model_calls"] == 0
    assert s["ttft_avg_s"] is None
    assert s["wall_s"] is None
