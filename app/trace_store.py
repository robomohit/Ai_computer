"""Workflow compiler — verified action traces that replay without the model.

The first successful run of a task COMPILES: the executed action sequence is
stored keyed by the normalized goal. The next time the same goal arrives, the
agent seeds its batched-action queue with the trace and replays it through the
full safety/approval/verification machinery with ZERO model round-trips — the
model is consulted exactly once at the end, to verify the observations and
finish. Any divergence (a failed action) clears the queue, invalidates the
trace, and hands control back to live planning.

A near-miss (similar but not identical goal) is surfaced as a few-shot hint in
the system prompt instead — retrieval-augmented acting for models that can't
be fine-tuned.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_MAX_TRACES = 200
_MAX_TRACE_CHARS = 60_000        # don't compile traces with huge payloads
_MIN_ACTIONS = 2                 # one-action tasks aren't worth compiling
_SIMILAR_JACCARD = 0.6

# Actions whose outcome depends on live external state — replaying them is
# harmless, but a trace that ONLY does these has nothing worth compiling.
_OBSERVATION_ONLY = {"screenshot", "screen_context", "cursor_position", "system_info"}

_WORD_RE = re.compile(r"[a-z0-9]+")


def normalize_goal(goal: str) -> str:
    return " ".join(_WORD_RE.findall(str(goal or "").lower()))


def _tokens(goal: str) -> set:
    return set(_WORD_RE.findall(str(goal or "").lower()))


class TraceStore:
    def __init__(self, path: Optional[Path] = None):
        env_path = os.environ.get("ORYNN_TRACE_STORE")
        self.path = Path(path or env_path or (Path.home() / ".ai_computer" / "traces.json"))
        self._lock = threading.Lock()
        self._traces: Dict[str, Dict[str, Any]] = {}
        self._load()

    # ── persistence ──────────────────────────────────────────────────────
    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._traces = {k: v for k, v in data.items() if isinstance(v, dict)}
        except Exception:
            self._traces = {}

    def _flush(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._traces, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)
        except Exception:
            pass  # a failed flush must never break a task

    # ── API ──────────────────────────────────────────────────────────────
    def save(self, goal: str, mode: str, actions: List[Dict[str, Any]]) -> bool:
        """Compile a successful run. Returns True when stored."""
        meaningful = [a for a in actions if a.get("type") not in _OBSERVATION_ONLY]
        if len(actions) < _MIN_ACTIONS or not meaningful:
            return False
        key = f"{mode}::{normalize_goal(goal)}"
        if not key.split("::", 1)[1]:
            return False
        record = {
            "goal": str(goal),
            "mode": str(mode),
            "actions": actions,
            "created_at": time.time(),
            "uses": 0,
        }
        if len(json.dumps(record)) > _MAX_TRACE_CHARS:
            return False
        with self._lock:
            self._traces[key] = record
            if len(self._traces) > _MAX_TRACES:
                # Evict least-recently-created, least-used first.
                victims = sorted(
                    self._traces.items(),
                    key=lambda kv: (kv[1].get("uses", 0), kv[1].get("created_at", 0)),
                )
                for k, _ in victims[: len(self._traces) - _MAX_TRACES]:
                    self._traces.pop(k, None)
            self._flush()
        return True

    def find_exact(self, goal: str, mode: str) -> Optional[Dict[str, Any]]:
        key = f"{mode}::{normalize_goal(goal)}"
        with self._lock:
            trace = self._traces.get(key)
            if trace:
                trace = dict(trace)
                trace["_key"] = key
                self._traces[key]["uses"] = self._traces[key].get("uses", 0) + 1
                self._flush()
        return trace

    def find_similar(self, goal: str, mode: str) -> Optional[Dict[str, Any]]:
        """Best near-miss above the Jaccard threshold (excluding exact)."""
        target = _tokens(goal)
        if not target:
            return None
        exact_key = f"{mode}::{normalize_goal(goal)}"
        best, best_score = None, _SIMILAR_JACCARD
        with self._lock:
            for key, trace in self._traces.items():
                if key == exact_key or trace.get("mode") != mode:
                    continue
                other = _tokens(trace.get("goal", ""))
                if not other:
                    continue
                score = len(target & other) / len(target | other)
                if score >= best_score:
                    best, best_score = dict(trace, _key=key), score
        return best

    def invalidate(self, trace: Dict[str, Any]) -> None:
        """A replay diverged — the world changed; drop the stale trace."""
        key = trace.get("_key")
        if not key:
            return
        with self._lock:
            self._traces.pop(key, None)
            self._flush()

    def hint_text(self, goal: str, mode: str) -> str:
        """Few-shot hint from the closest near-miss trace, or ''."""
        trace = self.find_similar(goal, mode)
        if not trace:
            return ""
        steps = []
        for a in trace.get("actions", [])[:8]:
            args_preview = json.dumps(a.get("args", {}))[:120]
            steps.append(f"{a.get('type')} {args_preview}")
        if not steps:
            return ""
        return (
            "<past_success_hint>\n"
            f"A similar past task succeeded: \"{trace.get('goal', '')[:120]}\"\n"
            "Its winning action sequence (adapt args to THIS goal, don't copy blindly):\n- "
            + "\n- ".join(steps)
            + "\n</past_success_hint>"
        )
