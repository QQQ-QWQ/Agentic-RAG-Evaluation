"""运行环境初始化（不做业务推理）。"""

from __future__ import annotations

import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from agentic_rag import config

SetupMode = Literal["default", "bare", "recovery"]


@dataclass
class SetupResult:
    ok: bool
    session_id: str
    project_root: Path
    cwd: Path
    message: str = ""
    fix_hint: str = ""


def run_setup(*, mode: SetupMode = "default") -> SetupResult:
    root = Path(config.PROJECT_ROOT).resolve()
    cwd = Path.cwd().resolve()

    if not (root / "pyproject.toml").is_file():
        return SetupResult(
            ok=False,
            session_id="",
            project_root=root,
            cwd=cwd,
            message="未在工程根找到 pyproject.toml",
            fix_hint="请在 Agentic-RAG-Evaluation 项目根目录执行命令。",
        )

    if sys.version_info < (3, 12):
        return SetupResult(
            ok=False,
            session_id="",
            project_root=root,
            cwd=cwd,
            message=f"需要 Python >= 3.12，当前 {sys.version_info.major}.{sys.version_info.minor}",
            fix_hint="使用 uv sync 所声明的 Python 版本。",
        )

    env_path = root / ".env"
    if mode != "bare" and not env_path.is_file():
        return SetupResult(
            ok=False,
            session_id="",
            project_root=root,
            cwd=cwd,
            message="缺少 .env 配置文件",
            fix_hint="复制 .env.example 为 .env 并填写 ARK_API_KEY、DEEPSEEK_API_KEY。",
        )

    if mode != "bare":
        if not config.DEEPSEEK_API_KEY:
            return SetupResult(
                ok=False,
                session_id="",
                project_root=root,
                cwd=cwd,
                message="DEEPSEEK_API_KEY 未配置",
                fix_hint=f"在 {env_path} 中设置密钥。",
            )
        if not config.ARK_API_KEY:
            return SetupResult(
                ok=False,
                session_id="",
                project_root=root,
                cwd=cwd,
                message="ARK_API_KEY 未配置",
                fix_hint=f"在 {env_path} 中设置密钥。",
            )

    sid = os.environ.get("TOPIC4_SESSION_ID") or uuid.uuid4().hex[:12]
    return SetupResult(
        ok=True,
        session_id=sid,
        project_root=root,
        cwd=cwd,
        message="环境就绪",
    )
