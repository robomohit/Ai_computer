"""Connectors registry — shared between the dashboard (where you set them up)
and the agent (which uses linked connectors when running tasks).

Linked state is persisted in workspace/connectors.json. The widget never
configures connectors; it just consumes whatever's linked.

A "linked" connector means the dashboard has stored credentials or a flag that
unlocks the agent to use that surface. For OAuth services we don't actually
ship OAuth flow yet (free-tier scope), so "link" stores a minimal placeholder
that the agent treats as permission to drive the corresponding browser surface.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

# The full registry. `auth_kind` describes how a connector links:
#   browser  — agent drives the web UI; "link" just marks consent
#   token    — needs an API token stored in linked state
#   local    — no auth, available immediately (filesystem, clipboard, etc.)
CONNECTORS: list[dict] = [
    {"id": "gmail",    "label": "Gmail",         "icon": "mail",
     "tint": "#EA4335", "auth_kind": "browser",
     "tip": "Drive Gmail web in the browser to triage + draft",
     "task_template": (
         "Open https://mail.google.com. Scan the inbox (top 10 unread). "
         "For each: classify (reply-needed / FYI / trash) and draft a "
         "reply where appropriate. Don't send — save as drafts. "
         "Report a summary."),
     "default_mode": "computer_use"},
    {"id": "outlook",  "label": "Outlook",       "icon": "mail",
     "tint": "#0078D4", "auth_kind": "browser",
     "tip": "Drive Outlook web in the browser",
     "task_template": (
         "Open https://outlook.office.com. Triage top 10 unread, draft "
         "replies, save as drafts only."),
     "default_mode": "computer_use"},
    {"id": "gcal",     "label": "Google Calendar","icon": "calendar",
     "tint": "#4285F4", "auth_kind": "browser",
     "tip": "Read this week's schedule",
     "task_template": (
         "Open https://calendar.google.com and report my upcoming events "
         "for the next 7 days. Group by day. Flag any conflicts."),
     "default_mode": "computer_use"},
    {"id": "github",   "label": "GitHub",        "icon": "github",
     "tint": "#181717", "auth_kind": "browser",
     "tip": "Triage GitHub notifications + PRs",
     "task_template": (
         "Open https://github.com/notifications. List open PRs and issues "
         "assigned to me or awaiting my review. Group by repo."),
     "default_mode": "computer_use"},
    {"id": "slack",    "label": "Slack",         "icon": "slack",
     "tint": "#4A154B", "auth_kind": "browser",
     "tip": "Summarize Slack unreads",
     "task_template": (
         "Open https://app.slack.com. Visit each unread channel, summarize "
         "what was discussed (skip bot/notification channels). Don't post."),
     "default_mode": "computer_use"},
    {"id": "notion",   "label": "Notion",        "icon": "notion",
     "tint": "#000000", "auth_kind": "browser",
     "tip": "Search my Notion workspace",
     "task_template": (
         "Open https://www.notion.so. Search my workspace for the topic "
         "I specify next, summarize the top 3 hits. Topic: "),
     "default_mode": "computer_use"},
    {"id": "drive",    "label": "Google Drive",  "icon": "drive",
     "tint": "#0F9D58", "auth_kind": "browser",
     "tip": "Find a file in Drive",
     "task_template": (
         "Open https://drive.google.com and find the file I name next. "
         "Open it and summarize. File: "),
     "default_mode": "computer_use"},
    {"id": "youtube",  "label": "YouTube",       "icon": "youtube",
     "tint": "#FF0000", "auth_kind": "browser",
     "tip": "Summarize a YouTube video",
     "task_template": (
         "Open the YouTube URL below, fetch the transcript, produce a "
         "5-bullet summary with timestamps for key claims. URL: "),
     "default_mode": "computer_use"},
    {"id": "filesystem","label": "Local Files",  "icon": "folder",
     "tint": "#4B5563", "auth_kind": "local",
     "tip": "Read / write local files (always available)",
     "task_template": "",
     "default_mode": "coding"},
    {"id": "clipboard","label": "Clipboard",     "icon": "clipboard",
     "tint": "#4B5563", "auth_kind": "local",
     "tip": "Read / write the system clipboard (always available)",
     "task_template": "",
     "default_mode": "auto"},
]


def store_path() -> Path:
    """workspace/connectors.json"""
    base = Path(os.environ.get("AI_COMPUTER_WORKSPACE", ".")).resolve()
    return base / "connectors.json"


def _load_state() -> dict[str, Any]:
    p = store_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict[str, Any]) -> None:
    p = store_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2), encoding="utf-8")


def list_with_state() -> list[dict]:
    """Return CONNECTORS with `linked` / `linked_at` / `notes` merged in."""
    state = _load_state()
    out = []
    for c in CONNECTORS:
        c = dict(c)
        s = state.get(c["id"], {})
        # Local connectors are implicitly linked — they need no setup.
        c["linked"] = bool(s.get("linked")) or c["auth_kind"] == "local"
        c["linked_at"] = s.get("linked_at")
        c["notes"] = s.get("notes", "")
        out.append(c)
    return out


def get(connector_id: str) -> Optional[dict]:
    for c in list_with_state():
        if c["id"] == connector_id:
            return c
    return None


def link(connector_id: str, notes: str = "") -> Optional[dict]:
    from datetime import datetime, timezone
    if not any(c["id"] == connector_id for c in CONNECTORS):
        return None
    state = _load_state()
    state[connector_id] = {
        "linked": True,
        "linked_at": datetime.now(timezone.utc).isoformat(),
        "notes": notes,
    }
    _save_state(state)
    return get(connector_id)


def unlink(connector_id: str) -> Optional[dict]:
    state = _load_state()
    state.pop(connector_id, None)
    _save_state(state)
    return get(connector_id)


def linked_only() -> list[dict]:
    """For the agent context — what surfaces is it allowed to drive?"""
    return [c for c in list_with_state() if c["linked"]]
