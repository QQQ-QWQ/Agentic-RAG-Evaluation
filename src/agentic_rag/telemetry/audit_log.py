"""
全局审计日志：仅记录与测试，**不**注入模型上下文、不参与规划。

默认写入 ``runs/logs/audit/global_audit.jsonl``（追加、一行一条 JSON）。
"""

from __future__ import annotations

import contextvars
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentic_rag import config as app_config

_audit_session_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "audit_session_id",
    default="",
)

_DEFAULT_REL = Path("runs/logs/audit/global_audit.jsonl")


def default_audit_log_path(project_root: Path | None = None) -> Path:
    root = (project_root or app_cfg_root()).resolve()
    return root / _DEFAULT_REL


def app_cfg_root() -> Path:
    return Path(app_config.PROJECT_ROOT).resolve()


def new_audit_session_id() -> str:
    return uuid.uuid4().hex[:16]


def set_audit_session_id(session_id: str) -> contextvars.Token[str]:
    return _audit_session_id.set(session_id or new_audit_session_id())


def reset_audit_session_id(token: contextvars.Token[str]) -> None:
    _audit_session_id.reset(token)


def get_audit_session_id() -> str:
    sid = _audit_session_id.get()
    return sid or "anonymous"


def audit_log(
    event: str,
    *,
    payload: dict[str, Any] | None = None,
    session_id: str | None = None,
    log_path: Path | None = None,
) -> str:
    """
    追加一条审计记录。返回写入的文件路径。
    """
    path = log_path or default_audit_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "session_id": session_id or get_audit_session_id(),
        "payload": payload or {},
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return str(path)


def audit_log_path_hint() -> str:
    return str(default_audit_log_path())
