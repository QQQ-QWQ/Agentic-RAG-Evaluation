"""
会话级追踪日志：``runs/logs/audit/sessions/<session_id>/trace.jsonl``

与 ``global_audit.jsonl`` 同步写入（经 ``audit_record``），字段更全，便于按会话查看工具链与编排。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentic_rag import config as app_config


def session_trace_path(
    session_id: str,
    *,
    project_root: Path | None = None,
) -> Path:
    root = (project_root or app_config.PROJECT_ROOT).resolve()
    sid = (session_id or "anonymous").strip() or "anonymous"
    return root / "runs" / "logs" / "audit" / "sessions" / sid / "trace.jsonl"


def append_session_trace(
    session_id: str,
    event: str,
    payload: dict[str, Any] | None = None,
    *,
    project_root: Path | None = None,
) -> str:
    path = session_trace_path(session_id, project_root=project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "session_id": session_id,
        "payload": payload or {},
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return str(path)


def load_session_trace(
    session_id: str,
    *,
    project_root: Path | None = None,
    tail: int | None = None,
) -> list[dict[str, Any]]:
    path = session_trace_path(session_id, project_root=project_root)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if tail is not None and tail > 0:
        return rows[-tail:]
    return rows


def filter_trace_events(
    rows: list[dict[str, Any]],
    *,
    event_prefix: str | None = None,
    events: set[str] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        ev = str(row.get("event") or "")
        if events is not None and ev not in events:
            continue
        if event_prefix and not ev.startswith(event_prefix):
            continue
        out.append(row)
    return out
