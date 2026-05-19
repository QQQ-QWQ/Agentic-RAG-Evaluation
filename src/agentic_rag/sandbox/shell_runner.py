"""在指定工作目录内执行受限 shell 命令（课程演示用，非生产级隔离）。"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from agentic_rag import config
from agentic_rag.tools.path_policy import is_shell_command_allowed


@dataclass(frozen=True)
class ShellResult:
    exit_code: int
    stdout: str
    stderr: str
    cwd: str
    shell: str

    def to_dict(self) -> dict:
        return {
            "exit_code": self.exit_code,
            "stdout": self.stdout[-12_000:],
            "stderr": self.stderr[-6000:],
            "cwd": self.cwd,
            "shell": self.shell,
        }


def _shell_argv(command: str) -> list[str]:
    if sys.platform == "win32":
        return [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ]
    return ["/bin/sh", "-c", command]


def exec_shell_command(
    workspace: Path,
    command: str,
    *,
    timeout_sec: float | None = None,
) -> ShellResult:
    allowed, reason = is_shell_command_allowed(command)
    if not allowed:
        raise ValueError(reason)

    ws = Path(workspace).resolve()
    ws.mkdir(parents=True, exist_ok=True)

    timeout = timeout_sec if timeout_sec is not None else float(
        getattr(config, "SHELL_TIMEOUT_SEC", 60)
    )
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}

    try:
        proc = subprocess.run(
            _shell_argv(command),
            cwd=str(ws),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"命令超时（>{timeout}s）") from exc
    shell_name = "powershell" if sys.platform == "win32" else "sh"
    return ShellResult(
        exit_code=int(proc.returncode),
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        cwd=str(ws),
        shell=shell_name,
    )
