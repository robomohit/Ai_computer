"""Real API connectors — free, no-auth, single-call tools that work on free models.
Structural wiring + formatting (HTTP mocked so the suite stays offline/deterministic)."""
from __future__ import annotations

from pathlib import Path

from app import connectors
from app.tools import ToolExecutor
from app.tool_registry import get_tool_schemas, get_unified_packs

CONNECTOR_TOOLS = ["weather", "wikipedia", "hacker_news", "github_repo", "dictionary"]


def test_connector_tools_present_in_unified_schema():
    names = {s["function"]["name"] for s in get_tool_schemas(get_unified_packs())}
    for t in CONNECTOR_TOOLS:
        assert t in names, f"{t} missing from the unified tool schema"


def test_api_connectors_are_auto_linked_no_setup():
    linked = {c["id"] for c in connectors.linked_only()}
    for cid in ["weather", "wikipedia", "hackernews", "github_api", "dictionary"]:
        assert cid in linked, f"{cid} should be auto-linked (auth_kind=api)"


def test_relevant_briefs_steer_to_the_tool():
    labels = [l for l, _ in connectors.relevant_briefs("what's the weather in paris")]
    assert "Weather" in labels


def _exec():
    return ToolExecutor(workspace=Path("."))


def test_weather_formats_real_shape(monkeypatch):
    ex = _exec()
    calls = {"n": 0}

    def fake_get(url, timeout=15.0):
        calls["n"] += 1
        if "geocoding" in url:
            return {"results": [{"latitude": 48.85, "longitude": 2.35, "name": "Paris", "country": "France"}]}
        return {"current": {"temperature_2m": 17.0, "apparent_temperature": 16.0, "relative_humidity_2m": 60,
                            "weather_code": 3, "wind_speed_10m": 9.0},
                "daily": {"time": ["2026-06-10"], "temperature_2m_max": [22.0], "temperature_2m_min": [12.0], "weather_code": [61]}}

    monkeypatch.setattr(ex, "_connector_get", fake_get)
    r = ex.weather("Paris")
    assert r.ok and "Paris" in r.output and "17.0" in r.output and "overcast" in r.output


def test_github_repo_accepts_url_and_slug(monkeypatch):
    ex = _exec()
    seen = {}

    def fake_get(url, timeout=15.0):
        seen["url"] = url
        if url.endswith("/issues?per_page=5&state=open&sort=updated"):
            return [{"number": 7, "title": "a bug", "pull_request": {}}, {"number": 8, "title": "real issue"}]
        return {"full_name": "robomohit/Orynn", "description": "x", "stargazers_count": 5,
                "forks_count": 0, "open_issues_count": 1, "language": "Python", "html_url": "https://github.com/robomohit/Orynn"}

    monkeypatch.setattr(ex, "_connector_get", fake_get)
    r = ex.github_repo("https://github.com/robomohit/Orynn")
    assert r.ok and "robomohit/Orynn" in r.output and "#8 real issue" in r.output
    assert "#7" not in r.output  # PRs filtered out


def test_dictionary_missing_word_is_graceful(monkeypatch):
    ex = _exec()

    def boom(url, timeout=15.0):
        raise RuntimeError("404")

    monkeypatch.setattr(ex, "_connector_get", boom)
    r = ex.dictionary("asdfghjkl")
    assert not r.ok and "No definition" in r.output
