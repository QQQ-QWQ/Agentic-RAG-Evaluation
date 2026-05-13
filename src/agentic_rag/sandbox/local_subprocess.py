"""在隔离目录中用当前解释器执行 Python 片段（验证代码、回归小脚本）。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from agentic_rag import config


@dataclass(frozen=True)
class SandboxResult:
    exit_code: int
    stdout: str
    stderr: str
    workspace_file: str

    def format_cli(self) -> str:
        return json.dumps(
            {
                "exit_code": self.exit_code,
                "stdout": self.stdout[-8000:],
                "stderr": self.stderr[-4000:],
                "script_path": self.workspace_file,
            },
            ensure_ascii=False,
            indent=2,
        )


def exec_python_snippet(
    workspace: Path,
    code: str,
    *,
    timeout_sec: float | None = None,
) -> SandboxResult:
    """
    将代码写入 workspace/_topic4_snippet.py 并 ``python`` 执行。

    - ``cwd`` 固定为 ``workspace``，避免默认污染仓库根目录。
    - 超时来自 ``config.SANDBOX_TIMEOUT_SEC``。
    """
    max_chars = getattr(config, "SANDBOX_MAX_CODE_CHARS", 50_000)
    if len(code) > max_chars:
        raise ValueError(f"代码过长（>{max_chars} 字符），拒绝写入")

    workspace = Path(workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    script = workspace / "_topic4_snippet.py"
    script.write_text(code, encoding="utf-8")

    timeout = timeout_sec if timeout_sec is not None else float(config.SANDBOX_TIMEOUT_SEC)
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}

    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        shell=False,
    )
    return SandboxResult(
        exit_code=int(proc.returncode),
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        workspace_file=str(script),
    )
