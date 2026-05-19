"""C4 受限 shell 命令执行工具。"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from agentic_rag import config
from agentic_rag.sandbox.shell_runner import ShellResult, exec_shell_command
from agentic_rag.tools.path_policy import normalize_user_path
from agentic_rag.tools.response_format import tool_response_json


def run_shell_in_workspace(
    command: str,
    workspace: Path,
    *,
    timeout_sec: float | None = None,
) -> dict[str, Any]:
    try:
        result: ShellResult = exec_shell_command(
            workspace,
            command,
            timeout_sec=timeout_sec,
        )
    except subprocess.TimeoutExpired as exc:
        return {"ok": False, "error": f"timeout: {exc}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    ok = result.exit_code == 0
    return {
        "ok": ok,
        "exit_code": result.exit_code,
        **result.to_dict(),
    }


def run_shell_under_project(
    command: str,
    *,
    working_dir: str = "",
    project_root: Path | None = None,
    timeout_sec: float | None = None,
) -> dict[str, Any]:
    """在工程根内子目录（默认工程根）执行命令。"""
    root = (project_root or config.PROJECT_ROOT).resolve()
    if (working_dir or "").strip():
        resolved = normalize_user_path(working_dir, project_root=root)
        if not resolved.ok:
            return {"ok": False, "error": resolved.error}
        cwd = resolved.path
        if not cwd.is_dir():
            return {"ok": False, "error": f"工作目录不存在：{cwd}"}
    else:
        cwd = root
    return run_shell_in_workspace(command, cwd, timeout_sec=timeout_sec)


def format_shell_response(payload: dict[str, Any]) -> str:
    ok = bool(payload.get("ok"))
    hints = [
        "仅在工程根内执行；禁止破坏性命令。复杂逻辑请用 topic4_code_runner。",
    ]
    if not ok and payload.get("stderr"):
        hints.append("请根据 stderr 修正命令。")
    return tool_response_json(
        "topic4_shell_exec",
        ok=ok,
        data={k: v for k, v in payload.items() if k != "ok"},
        error=None if ok else str(payload.get("error") or payload.get("stderr") or "命令失败"),
        hints=hints,
    )
