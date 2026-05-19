"""
系统知识库同步：扫描 ``data/raw/``（排除会话目录）→ 重写 ``documents.csv`` → 重建 Chroma。
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from agentic_rag import config as app_config
from agentic_rag.experiment.kb_chroma_admin import clear_chroma_and_index_caches
from agentic_rag.experiment.kb_index_builder import (
    load_or_build_knowledge_index,
    read_csv_rows,
)
from agentic_rag.experiment.kb_paths import infer_doc_type, iter_system_raw_files


def _next_doc_id(existing_rows: list[dict[str, str]]) -> str:
    """从已有行中取最大 doc_NNN。"""
    max_n = 0
    for row in existing_rows:
        did = (row.get("doc_id") or "").strip()
        if did.startswith("doc_"):
            try:
                max_n = max(max_n, int(did.split("_", 1)[1]))
            except ValueError:
                pass
    return f"doc_{max_n + 1:03d}"


def rebuild_documents_csv_from_raw(
    project_root: Path,
    *,
    source_note: str = "kb sync 系统扫描",
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """
    仅根据当前 ``data/raw`` 系统扫描结果**重写** ``documents.csv``（不含 session_upload / user_docs）。
    """
    proj = project_root.resolve()
    documents_csv = proj / "data" / "processed" / "documents.csv"
    old_rows = read_csv_rows(documents_csv) if documents_csv.is_file() else []
    by_rel: dict[str, dict[str, str]] = {}
    for row in old_rows:
        rel = (row.get("file_path") or "").replace("\\", "/").strip()
        if rel:
            by_rel[rel] = row

    scanned = iter_system_raw_files(proj)
    new_rows: list[dict[str, str]] = []
    added = 0
    kept = 0
    for fp in scanned:
        rel = fp.relative_to(proj).as_posix()
        if rel in by_rel:
            row = dict(by_rel[rel])
            row["file_path"] = rel
            kept += 1
        else:
            added += 1
            row = {
                "doc_id": _next_doc_id([*old_rows, *new_rows]),
                "title": fp.stem,
                "file_path": rel,
                "doc_type": infer_doc_type(rel),
                "source": source_note,
                "note": "",
            }
        new_rows.append(row)

    documents_csv.parent.mkdir(parents=True, exist_ok=True)
    keys = ["doc_id", "title", "file_path", "doc_type", "source", "note"]
    with documents_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for row in new_rows:
            w.writerow({k: row.get(k, "") for k in keys})

    meta = {
        "ok": True,
        "documents_csv": str(documents_csv),
        "file_count": len(new_rows),
        "kept_doc_ids": kept,
        "new_rows": added,
        "removed_from_csv": max(0, len(old_rows) - kept),
        "scanned_paths": [str(p) for p in scanned],
    }
    return new_rows, meta


def sync_system_kb(
    project_root: Path | None = None,
    *,
    clear_chroma_first: bool = False,
    remove_chunks_jsonl: bool = False,
    force_rebuild_index: bool = True,
) -> dict[str, Any]:
    """
    系统知识库一键同步：可选清 Chroma → 重写清单 → 切块 + embedding 写入 Chroma。
    """
    root = (project_root or app_config.PROJECT_ROOT).resolve()
    out: dict[str, Any] = {"ok": True, "steps": []}

    if clear_chroma_first:
        cleared = clear_chroma_and_index_caches(
            root, remove_chunks_jsonl=remove_chunks_jsonl
        )
        out["steps"].append({"clear_chroma": cleared})

    rows, csv_meta = rebuild_documents_csv_from_raw(root)
    out["steps"].append({"rebuild_csv": csv_meta})
    out["document_count"] = len(rows)

    if not rows:
        out["ok"] = False
        out["error"] = "未扫描到任何系统级 raw 文件（请检查 data/raw/）"
        return out

    documents_csv = root / "data" / "processed" / "documents.csv"
    chunks_jsonl = root / "data" / "processed" / "chunks.jsonl"
    if force_rebuild_index:
        idx = load_or_build_knowledge_index(
            root,
            documents_csv=documents_csv,
            chunks_jsonl=chunks_jsonl,
            use_cache=False,
            force_rebuild=True,
        )
        out["steps"].append(
            {
                "index": {
                    "chunks": len(idx.chunks),
                    "source": getattr(idx, "source", ""),
                }
            }
        )
    return out


def reset_system_kb(project_root: Path | None = None) -> dict[str, Any]:
    """清空 Chroma + chunks.jsonl，再全量 sync（干净重启）。"""
    return sync_system_kb(
        project_root,
        clear_chroma_first=True,
        remove_chunks_jsonl=True,
        force_rebuild_index=True,
    )
