"""
知识库路径约定（系统全库 vs 会话临时文件）。

- **系统级**：``data/raw/`` 下除排除目录外的文件，经 ``kb sync`` 写入 ``documents.csv`` + Chroma。
- **会话级**：``data/raw/session_upload/`` 或客户端传入的盘外路径，仅内存切块索引，**不**改清单、**不**写全库 Chroma。
"""

from __future__ import annotations

from pathlib import Path

# 相对工程根的排除目录（位于 data/raw/ 之下，整段路径名匹配即跳过）
KB_RAW_EXCLUDE_DIR_NAMES: frozenset[str] = frozenset(
    {
        "session_upload",  # 用户会话附加材料（单次索引）
        "user_docs",  # 历史客户端复制目录，不再作为系统全库来源
        "web_snapshots",  # Firecrawl 快照，由工具按需入库或 sync 排除
    }
)

# 参与系统 sync 的扩展名（与 multi_doc 路径识别大致对齐）
KB_SYSTEM_FILE_SUFFIXES: frozenset[str] = frozenset(
    {
        ".md",
        ".markdown",
        ".txt",
        ".csv",
        ".py",
        ".json",
        ".yaml",
        ".yml",
        ".xml",
        ".html",
        ".htm",
        ".pdf",
        ".docx",
        ".pptx",
    }
)

_DOC_TYPE_BY_FOLDER: dict[str, str] = {
    "tech_docs": "tech_doc",
    "learning_docs": "learning_doc",
    "lab_docs": "lab_doc",
    "tables_csv": "table_csv",
    "code_snippets": "code_snippet",
}


def system_raw_root(project_root: Path) -> Path:
    return (project_root / "data" / "raw").resolve()


def session_upload_root(project_root: Path) -> Path:
    return (project_root / "data" / "raw" / "session_upload").resolve()


def is_under_session_upload(path: Path, project_root: Path) -> bool:
    try:
        path.resolve().relative_to(session_upload_root(project_root))
        return True
    except ValueError:
        return False


def is_excluded_from_system_sync(rel_posix: str) -> bool:
    """``rel_posix`` 为相对工程根的路径，如 ``data/raw/session_upload/x.md``。"""
    parts = Path(rel_posix).as_posix().split("/")
    if "raw" not in parts:
        return False
    try:
        raw_idx = parts.index("raw")
    except ValueError:
        return False
    under_raw = parts[raw_idx + 1 :]
    return any(seg in KB_RAW_EXCLUDE_DIR_NAMES for seg in under_raw)


def infer_doc_type(rel_posix: str) -> str:
    parts = Path(rel_posix).parts
    if "raw" in parts:
        idx = parts.index("raw")
        if idx + 1 < len(parts):
            folder = parts[idx + 1]
            return _DOC_TYPE_BY_FOLDER.get(folder, "raw_doc")
    return "raw_doc"


def iter_system_raw_files(project_root: Path) -> list[Path]:
    """扫描系统级 raw 文件（已排除 session_upload / user_docs 等）。"""
    root = system_raw_root(project_root)
    if not root.is_dir():
        return []
    proj = project_root.resolve()
    out: list[Path] = []
    for fp in sorted(root.rglob("*")):
        if not fp.is_file():
            continue
        if fp.suffix.lower() not in KB_SYSTEM_FILE_SUFFIXES:
            continue
        if fp.name.lower() == "readme.md":
            continue
        try:
            rel = fp.resolve().relative_to(proj).as_posix()
        except ValueError:
            continue
        if is_excluded_from_system_sync(rel):
            continue
        out.append(fp.resolve())
    return out
