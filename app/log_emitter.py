from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List

import json
from pathlib import Path

_log = logging.getLogger("log_emitter")

MAX_LOG_FILE_BYTES = 20 * 1024 * 1024
MAX_TEXT_FIELD_CHARS = 4_000


class LogEmitter:
    """Simple pub/sub bus for SSE task log streaming."""
    def __init__(self):
        self._queues: Dict[str, List[asyncio.Queue]] = {}
        self._seqs: Dict[str, int] = {}
        self._disk_logging_disabled: set[str] = set()
        self.log_dir = Path("workspace/logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def subscribe(self, task_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._queues.setdefault(task_id, []).append(q)
        return q

    def unsubscribe(self, task_id: str, q: asyncio.Queue):
        if task_id in self._queues:
            try:
                self._queues[task_id].remove(q)
            except ValueError:
                pass

    def log_path(self, task_id: str) -> Path:
        return self.log_dir / f"{task_id}.jsonl"

    def read_log(self, task_id: str, since: int = 0) -> list[dict]:
        log_file = self.log_path(task_id)
        if not log_file.exists():
            return []

        events: list[dict] = []
        with open(log_file, "r", encoding="utf-8") as f:
            for index, line in enumerate(f):
                if index < since:
                    continue
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    if isinstance(msg, dict):
                        msg.setdefault("task_id", task_id)
                        msg.setdefault("seq", index)
                    events.append(msg)
                except json.JSONDecodeError:
                    continue
        return events

    def count_events(self, task_id: str) -> int:
        log_file = self.log_path(task_id)
        if not log_file.exists():
            return 0
        with open(log_file, "r", encoding="utf-8") as f:
            return sum(1 for _ in f)

    def task_ids(self) -> list[str]:
        return sorted(path.stem for path in self.log_dir.glob("*.jsonl"))

    def _truncate_text(self, value: str) -> str:
        if len(value) <= MAX_TEXT_FIELD_CHARS:
            return value
        return value[:MAX_TEXT_FIELD_CHARS] + "\n...(truncated for disk log)"

    def _sanitize_for_disk(self, event_type: str, payload: dict) -> dict:
        """Keep live SSE payloads rich, but make persistent logs bounded."""
        sanitized = dict(payload)

        if event_type == "screenshot" and isinstance(sanitized.get("data"), str):
            raw = sanitized["data"]
            sanitized["data"] = "[omitted from persistent log]"
            sanitized["data_omitted"] = True
            sanitized["data_chars"] = len(raw)

        for field in ("detail", "output", "content", "reason", "message"):
            if isinstance(sanitized.get(field), str):
                sanitized[field] = self._truncate_text(sanitized[field])

        if event_type == "file_change" and isinstance(sanitized.get("content"), str):
            sanitized["content"] = self._truncate_text(sanitized["content"])

        return sanitized

    def emit(self, task_id: str, event_type: str, payload: dict):
        seq = self._seqs.get(task_id)
        if seq is None:
            seq = self.count_events(task_id)
        msg = {
            "type": event_type,
            "task_id": task_id,
            "seq": seq,
            "ts": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        self._seqs[task_id] = seq + 1
        
        # Persistent logging
        log_file = self.log_path(task_id)
        if task_id not in self._disk_logging_disabled:
            if log_file.exists() and log_file.stat().st_size >= MAX_LOG_FILE_BYTES:
                self._disk_logging_disabled.add(task_id)
                truncation_notice = {
                    "type": "status",
                    "task_id": task_id,
                    "seq": seq,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "message": "Persistent log limit reached; further events omitted to protect disk space.",
                    "persistent_log_truncated": True,
                }
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(truncation_notice) + "\n")
            else:
                disk_msg = self._sanitize_for_disk(event_type, msg)
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(disk_msg) + "\n")
            
        for q in list(self._queues.get(task_id, [])):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                _log.warning("SSE subscriber queue full for task %s — event dropped", task_id)

    def cleanup_task(self, task_id: str) -> None:
        """Release in-memory state for a completed/failed task.

        Called after a task reaches a terminal state so the sequence counter
        and disk-logging flag don't accumulate indefinitely across many runs.
        Any live SSE subscriber queues are left alone — they manage their own
        lifecycle via subscribe/unsubscribe.
        """
        self._seqs.pop(task_id, None)
        self._disk_logging_disabled.discard(task_id)


log_emitter = LogEmitter()
