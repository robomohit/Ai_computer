"""Unit tests for the workflow compiler's trace store."""
from __future__ import annotations

from app.trace_store import TraceStore, normalize_goal


def _store(tmp_path):
    return TraceStore(path=tmp_path / "traces.json")


ACTIONS = [
    {"type": "read_file", "args": {"path": "a.txt"}},
    {"type": "write_file", "args": {"path": "b.txt", "content": "x"}},
]


def test_save_and_exact_recall_roundtrip(tmp_path):
    s = _store(tmp_path)
    assert s.save("Organize my Downloads folder", "auto", ACTIONS) is True

    # Punctuation/case/whitespace must not break recall.
    hit = s.find_exact("  organize MY downloads folder!! ", "auto")
    assert hit is not None
    assert hit["actions"] == ACTIONS

    # Different mode is a different trace.
    assert s.find_exact("organize my downloads folder", "computer") is None

    # Persistence: a fresh store instance sees the same trace.
    s2 = _store(tmp_path)
    assert s2.find_exact("organize my downloads folder", "auto") is not None


def test_single_action_and_observation_only_traces_rejected(tmp_path):
    s = _store(tmp_path)
    assert s.save("goal one", "auto", ACTIONS[:1]) is False
    assert s.save("goal two", "auto", [
        {"type": "screenshot", "args": {}},
        {"type": "screen_context", "args": {}},
    ]) is False


def test_invalidate_drops_stale_trace(tmp_path):
    s = _store(tmp_path)
    s.save("clean the desktop", "auto", ACTIONS)
    hit = s.find_exact("clean the desktop", "auto")
    assert hit is not None
    s.invalidate(hit)
    assert s.find_exact("clean the desktop", "auto") is None


def test_similar_trace_becomes_hint_not_replay(tmp_path):
    s = _store(tmp_path)
    s.save("organize my downloads folder by file type", "auto", ACTIONS)

    # Near-miss goal: high token overlap but not exact.
    assert s.find_exact("organize my downloads folder by type", "auto") is None
    hint = s.hint_text("organize my downloads folder by type", "auto")
    assert "past_success_hint" in hint
    assert "read_file" in hint

    # Unrelated goal gets no hint.
    assert s.hint_text("what is the weather in tokyo", "auto") == ""


def test_normalize_goal():
    assert normalize_goal("  Open... CALCULATOR!  ") == "open calculator"
