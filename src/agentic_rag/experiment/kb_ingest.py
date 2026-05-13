"""
将用户提供的本地文件登记进 ``documents.csv``，复制到 ``data/raw/user_docs/``（可选引用仓库内路径），
并调用 ``load_or_build_knowledge_index(..., force_rebuild=True)`` 重建切块与 Chroma 全库索引。
"""

from __future__ import annotations

import csv
import re
import shutil
from pathlib import Path
from typing import Any

from agentic_rag.experiment.kb_index_builder import (
    load_or_build_knowledge_index,
    read_csv_rows,
)

_STANDARD_FIELDS = ["doc_id", "title", "file_path", "doc_type", "source", "note"]


_DOC_ID_RE = re.compile(r"^doc_(\d+)$", re.I)


def next_doc_id(documents_csv: Path) -> str:
    """在现有 ``doc_NNN`` 基础上递增。"""
    if not documents_csv.is_file():
        return "doc_001"
    rows = read_csv_rows(documents_csv)
    max_n = 0
    for row in rows:
        m = _DOC_ID_RE.match((row.get("doc_id") or "").strip())
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"doc_{max_n + 1:03d}"


def _append_inventory_row(documents_csv: Path, new_row: dict[str, str]) -> None:
    documents_csv.parent.mkdir(parents=True, exist_ok=True)
    keys = list(_STANDARD_FIELDS)
    rows: list[dict[str, str]] = []
    if documents_csv.is_file():
        rows = read_csv_rows(documents_csv)
        if rows:
            keys = list(rows[0].keys())
    rows.append({k: new_row.get(k, "") for k in keys})

    with documents_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: str(r.get(k, "")) for k in keys})


def ingest_local_file_to_kb(
    project_root: Path,
    source_file: Path,
    *,
    title: str | None = None,
    doc_type: str = "user_doc",
    source_note: str = "用户入库",
    note: str = "",
    copy_file: bool = True,
    force_rebuild_index: bool = True,
) -> dict[str, Any]:
    """
    Parameters
    ----------
    copy_file
        True：复制到 ``data/raw/user_docs/`` 并在 CSV 中登记相对路径。
        False：CSV 登记为相对 ``project_root`` 的路径（文件须已在仓库内）。
    force_rebuild_index
        True：重建 ``chunks.jsonl``、重新 embedding 并写入 Chroma（指纹随 CSV/文件变）。
    """
    root = project_root.resolve()
    src = source_file.expanduser().resolve()
    if not src.is_file():
        return {"ok": False, "error": f"不是可读文件：{src}"}

    documents_csv = root / "data" / "processed" / "documents.csv"
    chunks_jsonl = root / "data" / "processed" / "chunks.jsonl"

    doc_id = next_doc_id(documents_csv)
    display_title = (title or "").strip() or src.stem

    if copy_file:
        dest_dir = root / "data" / "raw" / "user_docs"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_name = f"{src.stem}_{doc_id}{src.suffix.lower()}"
        dest_path = dest_dir / dest_name
        shutil.copy2(src, dest_path)
        rel = f"data/raw/user_docs/{dest_name}"
    else:
        try:
            rel = str(src.relative_to(root)).replace("\\", "/")
        except ValueError:
            return {
                "ok": False,
                "error": "未使用复制模式时，文件必须位于工程根目录之下。",
            }

    _append_inventory_row(
        documents_csv,
        {
            "doc_id": doc_id,
            "title": display_title,
            "file_path": rel.replace("\\", "/"),
            "doc_type": doc_type,
            "source": source_note,
            "note": note,
        },
    )

    out: dict[str, Any] = {
        "ok": True,
        "doc_id": doc_id,
        "title": display_title,
        "file_path": rel,
        "documents_csv": str(documents_csv),
    }

    if force_rebuild_index:
        load_or_build_knowledge_index(
            root,
            documents_csv=documents_csv,
            chunks_jsonl=chunks_jsonl,
            use_cache=True,
            force_rebuild=True,
        )
        out["index"] = "rebuilt"

    return out
