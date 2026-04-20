from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Dict, List

import json
from pathlib import Path

class LogEmitter:
    """Simple pub/sub bus for SSE task log streaming."""
    def __init__(self):
        self._queues: Dict[str, List[asyncio.Queue]] = {}
        self._seqs: Dict[str, int] = {}
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
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(msg) + "\n")
            
        for q in list(self._queues.get(task_id, [])):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

log_emitter = LogEmitter()
