"""工程内路径解析与写盘/命令执行安全策略。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from agentic_rag import config

# 禁止 Agent 直接写入或覆盖的路径前缀（相对工程根，POSIX）
_WRITE_DENY_PREFIXES: tuple[str, ...] = (
    ".git/",
    ".cursor/",
    ".venv/",
    "venv/",
    "__pycache__/",
    "node_modules/",
)

_WRITE_DENY_EXACT: frozenset[str] = frozenset(
    {
        ".env",
        ".env.example",
        "uv.lock",
        "pyproject.toml",
        "data/processed/documents.csv",
        "data/processed/chunks.jsonl",
    }
)

# 建议写盘区域（不在列表内也允许，只要未命中 deny）
_WRITE_PREFERRED_PREFIXES: tuple[str, ...] = (
    "data/raw/",
    "runs/",
    "data/raw/session_upload/",
    "data/raw/user_docs/",
    "data/raw/web_snapshots/",
)

_SHELL_DENY_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\brm\s+-rf\b",
        r"\brmdir\s+/s\b",
        r"\bdel\s+/[fq]",
        r"\bformat\b",
        r"\bshutdown\b",
        r"\breboot\b",
        r"\bmkfs\b",
        r"\bdd\s+if=",
        r"\bgit\s+push\s+.*--force",
        r"\bgit\s+reset\s+--hard",
        r">\s*\.env",
        r"\|\s*sh\b",
        r"\|\s*bash\b",
        r"\bpip\s+install\b",
        r"\buv\s+add\b",
        r"\bconda\s+install\b",
    )
)


@dataclass(frozen=True)
class ResolvedPath:
    ok: bool
    path: Path
    rel_posix: str
    error: str | None = None


def normalize_user_path(
    file_path: str,
    *,
    project_root: Path | None = None,
) -> ResolvedPath:
    """将用户/模型给出的路径解析为工程根内的绝对路径。"""
    root = (project_root or config.PROJECT_ROOT).resolve()
    raw = (file_path or "").strip().strip('"').strip("'")
    if not raw:
        return ResolvedPath(ok=False, path=root, rel_posix="", error="路径为空")

    fp = Path(raw).expanduser()
    if not fp.is_absolute():
        fp = (root / fp).resolve()
    else:
        fp = fp.resolve()

    try:
        rel = fp.relative_to(root).as_posix()
    except ValueError:
        return ResolvedPath(
            ok=False,
            path=fp,
            rel_posix="",
            error=f"路径必须在工程根内：{root}",
        )

    return ResolvedPath(ok=True, path=fp, rel_posix=rel)


def is_write_path_allowed(rel_posix: str) -> tuple[bool, str]:
    rel = rel_posix.replace("\\", "/").lstrip("/")
    if rel in _WRITE_DENY_EXACT:
        return False, f"禁止写入受保护文件：{rel}"
    for prefix in _WRITE_DENY_PREFIXES:
        if rel == prefix.rstrip("/") or rel.startswith(prefix):
            return False, f"禁止写入受保护目录：{prefix}"
    return True, ""


def assert_write_path_allowed(rel_posix: str) -> None:
    ok, msg = is_write_path_allowed(rel_posix)
    if not ok:
        raise PermissionError(msg)


def is_shell_command_allowed(command: str) -> tuple[bool, str]:
    text = (command or "").strip()
    if not text:
        return False, "命令为空"
    if len(text) > 4000:
        return False, "命令过长"
    for pat in _SHELL_DENY_PATTERNS:
        if pat.search(text):
            return False, f"命令命中安全拒绝规则：{pat.pattern}"
    return True, ""
