"""
客户端多轮对话全文落盘（供刷新页面后人工查阅；**不**自动回填 Gradio UI）。

路径：``runs/logs/audit/sessions/<session_id>/chat.jsonl``
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentic_rag import config as app_config


def session_chat_log_path(
    session_id: str,
    *,
    project_root: Path | None = None,
) -> Path:
    root = (project_root or app_config.PROJECT_ROOT).resolve()
    sid = (session_id or "anonymous").strip() or "anonymous"
    return root / "runs" / "logs" / "audit" / "sessions" / sid / "chat.jsonl"


def append_chat_turn(
    session_id: str,
    *,
    user_text: str,
    assistant_text: str,
    extra: dict[str, Any] | None = None,
    project_root: Path | None = None,
) -> str:
    """追加一轮 user/assistant 全文，返回写入路径。"""
    path = session_chat_log_path(session_id, project_root=project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "user": user_text,
        "assistant": assistant_text,
    }
    if extra:
        record.update(extra)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return str(path)


def turns_to_gradio_messages(
    turns: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """将 ``chat.jsonl`` 轮次转为 Gradio 6 Chatbot messages 格式。"""
    out: list[dict[str, str]] = []
    for t in turns:
        user = str(t.get("user") or "")
        assistant = str(t.get("assistant") or "")
        if user:
            out.append({"role": "user", "content": user})
        if assistant:
            out.append({"role": "assistant", "content": assistant})
    return out


def load_chat_turns(
    session_id: str,
    *,
    project_root: Path | None = None,
) -> list[dict[str, Any]]:
    """读取某会话已落盘的全部轮次（供导出或后续恢复 UI）。"""
    path = session_chat_log_path(session_id, project_root=project_root)
    if not path.is_file():
        return []
    turns: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                turns.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return turns
