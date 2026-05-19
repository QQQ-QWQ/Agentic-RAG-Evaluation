"""受限 Python 执行（对应开题 code_runner；底层复用本地 subprocess 沙箱）。"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from agentic_rag import config
from agentic_rag.sandbox.local_subprocess import SandboxResult, exec_python_snippet
from agentic_rag.tools.response_format import tool_response_json


def _resolve_readable_path(raw: str, *, project_root: Path) -> Path:
    text = (raw or "").strip().strip('"').strip("'")
    if not text:
        raise ValueError("路径为空")
    fp = Path(text).expanduser()
    if not fp.is_absolute():
        fp = (project_root / fp).resolve()
    else:
        fp = fp.resolve()
    if not fp.is_file():
        raise FileNotFoundError(f"文件不存在：{fp}")
    return fp


def _stage_files(workspace: Path, paths: list[str], *, project_root: Path) -> list[str]:
    """将允许访问的只读文件复制到沙箱 data/ 子目录。"""
    staged: list[str] = []
    data_dir = workspace / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    for p in paths:
        src = _resolve_readable_path(p, project_root=project_root)
        dest = data_dir / src.name
        if dest.resolve() != src.resolve():
            shutil.copy2(src, dest)
        staged.append(str(dest.relative_to(workspace)))
    return staged


def run_code_in_sandbox(
    code: str,
    workspace: Path,
    *,
    read_only_paths: list[str] | None = None,
    timeout_sec: float | None = None,
) -> dict[str, Any]:
    root = config.PROJECT_ROOT.resolve()
    ws = Path(workspace).resolve()
    staged: list[str] = []
    if read_only_paths:
        staged = _stage_files(ws, read_only_paths, project_root=root)
    try:
        result: SandboxResult = exec_python_snippet(
            ws,
            code,
            timeout_sec=timeout_sec,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc), "staged_files": staged}
    return {
        "ok": result.exit_code == 0,
        "exit_code": result.exit_code,
        "stdout": result.stdout[-12_000:],
        "stderr": result.stderr[-6000:],
        "script_path": result.workspace_file,
        "staged_files": staged,
        "workspace": str(ws),
    }


def format_code_runner_response(payload: dict[str, Any]) -> str:
    ok = bool(payload.get("ok"))
    hints = [
        "在会话沙箱目录执行；可用 read_only_paths 挂载工程内 CSV/py 等只读副本。",
        "复杂数值请优先 topic4_calculator / topic4_table_analyzer。",
    ]
    if not ok and payload.get("stderr"):
        hints.append("请根据 stderr 修正代码后重试。")
    return tool_response_json(
        "topic4_code_runner",
        ok=ok,
        data={k: v for k, v in payload.items() if k not in ("ok", "error")},
        error=str(payload.get("error") or "") or None,
        hints=hints,
    )
