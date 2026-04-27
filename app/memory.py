from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .log_emitter import MAX_TEXT_FIELD_CHARS
from .models import MemoryItem


class _FallbackCollection:
    """Pure keyword-based fallback used only when ChromaDB is unavailable.
    No rigged scores — plain TF-style word overlap only.
    """

    def __init__(self):
        self.docs: list = []

    def count(self):
        return len(self.docs)

    def add(self, documents, metadatas, ids):
        self.docs.extend(zip(ids, documents, metadatas))

    def query(self, query_texts, n_results, where=None):
        q_tokens = set(query_texts[0].lower().split())
        scored = []
        for _id, doc, meta in self.docs:
            if where:
                # Simple equality filter
                match = all(meta.get(k) == v for k, v in where.items())
                if not match:
                    continue
            d_tokens = set(doc.lower().split())
            score = len(q_tokens & d_tokens)
            scored.append((score, _id, doc, meta))
        ranked = sorted(scored, reverse=True)[:n_results]
        return {
            "ids": [[r[1] for r in ranked]],
            "documents": [[r[2] for r in ranked]],
            "metadatas": [[r[3] for r in ranked]],
        }

    def get(self, limit, offset=0, where=None, **kwargs):
        if where:
            filtered = [(i, d, m) for i, d, m in self.docs if all(m.get(k) == v for k, v in where.items())]
        else:
            filtered = self.docs
        chunk = filtered[offset: offset + limit]
        return {
            "ids": [c[0] for c in chunk],
            "documents": [c[1] for c in chunk],
            "metadatas": [c[2] for c in chunk],
        }

    def delete(self, ids):
        id_set = set(ids)
        self.docs = [(i, d, m) for i, d, m in self.docs if i not in id_set]


class ShortTermBuffer:
    """In-memory ring buffer of the last N turns per session."""

    _MAX_TURNS = 20

    def __init__(self):
        self._sessions: Dict[str, deque] = {}

    def add(self, session_id: str, content: str) -> None:
        if session_id not in self._sessions:
            self._sessions[session_id] = deque(maxlen=self._MAX_TURNS)
        self._sessions[session_id].append(content)

    def get(self, session_id: str) -> List[str]:
        return list(self._sessions.get(session_id, []))

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


class MemoryStore:
    def __init__(self, db_path: Path):
        chroma_dir = db_path.parent / "chroma_memory"
        chroma_dir.mkdir(parents=True, exist_ok=True)
        self._counter = 0
        self.short_term = ShortTermBuffer()
        import os
        use_chroma = os.environ.get("USE_CHROMA", "0") == "1"
        if use_chroma:
            try:
                import chromadb
                from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

                self.client = chromadb.PersistentClient(path=str(chroma_dir))
                ef = SentenceTransformerEmbeddingFunction(
                    model_name="all-MiniLM-L6-v2", device="cpu", normalize_embeddings=True
                )
                self.collection = self.client.get_or_create_collection(
                    name="agent_memory",
                    embedding_function=ef,
                    metadata={"hnsw:space": "cosine"},
                )
                self._counter = self.collection.count()
                self._use_chroma = True
            except Exception:
                self.collection = _FallbackCollection()
                self._use_chroma = False
        else:
            self.collection = _FallbackCollection()
            self._use_chroma = False

    # ── Short-term helpers ────────────────────────────────────────────────

    def add_turn(self, session_id: str, content: str) -> None:
        """Add a turn to the in-memory short-term buffer (last 20 turns)."""
        self.short_term.add(session_id, content)

    def get_short_term(self, session_id: str) -> List[str]:
        """Return up to 20 most recent turns for this session."""
        return self.short_term.get(session_id)

    # ── Long-term helpers ─────────────────────────────────────────────────

    def summarize_session(
        self,
        task_id: str,
        goal: str,
        success: bool,
        reason: str,
        mode: str,
    ) -> None:
        """Write a compact session summary to long-term memory and clear short-term."""
        outcome_word = "successfully" if success else "unsuccessfully"
        reason_snippet = (reason[:200] + "…") if len(reason) > 200 else reason
        goal_snippet = (goal[:150] + "…") if len(goal) > 150 else goal
        summary = (
            f"Session ({mode}): {goal_snippet}. "
            f"Completed {outcome_word}. {reason_snippet}"
        )
        self.add(
            kind="session_summary",
            content=summary,
            metadata={
                "task_id": task_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "mode": mode,
                "success": str(success),
            },
        )
        self.short_term.clear(task_id)

    def recall_sessions(self, query: str, n: int = 5) -> List[MemoryItem]:
        """Semantic search restricted to session_summary items."""
        total = self.collection.count()
        if total == 0:
            return []
        # Fetch n*3 candidates then filter client-side so we always get n if available
        try:
            if self._use_chroma:
                results = self.collection.query(
                    query_texts=[query],
                    n_results=min(n * 3, total),
                    where={"kind": "session_summary"},
                )
            else:
                results = self.collection.query(
                    query_texts=[query],
                    n_results=min(n * 3, total),
                    where={"kind": "session_summary"},
                )
        except Exception:
            # Chroma raises if the where filter yields zero candidates
            return []
        items = []
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i]
            items.append(
                MemoryItem(
                    id=int(results["ids"][0][i]),
                    kind=meta.get("kind", ""),
                    content=doc,
                    metadata={k: v for k, v in meta.items() if k not in ("kind", "created_at")},
                    created_at=meta.get("created_at", ""),
                )
            )
        return items[:n]

    # ── Core write / search ───────────────────────────────────────────────

    def add(self, kind: str, content: str, metadata: Dict[str, Any] | None = None) -> int:
        self._counter += 1
        doc_id = str(self._counter)
        meta = {
            "kind": kind,
            "created_at": datetime.now(timezone.utc).isoformat(),
            **(metadata or {}),
        }
        safe_meta = {
            k: str(v) if not isinstance(v, (str, int, float, bool)) else v
            for k, v in meta.items()
        }
        self.collection.add(documents=[content], metadatas=[safe_meta], ids=[doc_id])
        return self._counter

    def add_action_result(self, task_id: str, action_id: str, result: str) -> int:
        idx = self.add("action_result", result, {"task_id": task_id, "action_id": action_id})
        self.enforce_sliding_window(task_id)
        return idx

    def search(self, prompt: str, limit: int = 5) -> List[MemoryItem]:
        total = self.collection.count()
        if total == 0:
            return []
        results = self.collection.query(
            query_texts=[prompt],
            n_results=min(limit, total),
        )
        items = []
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i]
            items.append(
                MemoryItem(
                    id=int(results["ids"][0][i]),
                    kind=meta.get("kind", ""),
                    content=doc,
                    metadata={
                        k: v for k, v in meta.items() if k not in ("kind", "created_at")
                    },
                    created_at=meta.get("created_at", ""),
                )
            )
        return items

    def recent(self, limit: int = 20) -> List[MemoryItem]:
        total = self.collection.count()
        if total == 0:
            return []
        all_results = self.collection.get(
            limit=min(limit, total),
            offset=max(0, total - limit),
        )
        items = []
        for i, doc in enumerate(all_results["documents"]):
            meta = all_results["metadatas"][i]
            items.append(
                MemoryItem(
                    id=int(all_results["ids"][i]),
                    kind=meta.get("kind", ""),
                    content=doc,
                    metadata={
                        k: v for k, v in meta.items() if k not in ("kind", "created_at")
                    },
                    created_at=meta.get("created_at", ""),
                )
            )
        return list(reversed(items))

    def enforce_sliding_window(self, task_id: str):
        total = self.collection.count()
        if total == 0:
            return
        meta_results = self.collection.get(limit=total, offset=0)
        task_ids_list = []
        task_docs = []
        for i, m in enumerate(meta_results["metadatas"]):
            if m.get("task_id") == task_id and m.get("kind") != "session_summary":
                task_ids_list.append(meta_results["ids"][i])
                task_docs.append(meta_results["documents"][i])

        char_count = sum(len(d) for d in task_docs)
        if char_count > MAX_TEXT_FIELD_CHARS:
            half = len(task_ids_list) // 2
            oldest_ids = task_ids_list[:half]
            oldest_docs = task_docs[:half]

            summary_text = f"Summary of {len(oldest_docs)} previous actions: " + " ".join(oldest_docs)
            if len(summary_text) > MAX_TEXT_FIELD_CHARS:
                summary_text = summary_text[:MAX_TEXT_FIELD_CHARS] + "..."

            deleted = False
            try:
                self.collection.delete(ids=oldest_ids)
                deleted = True
            except AttributeError:
                pass

            if deleted:
                self.add("summary", summary_text, {"task_id": task_id})
