"""
Chroma 与进程内索引缓存管理（清空 / 列举）。
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from agentic_rag import config as app_config


def clear_chroma_and_index_caches(
    project_root: Path | None = None,
    *,
    remove_chunks_jsonl: bool = False,
) -> dict[str, Any]:
    """
    删除持久化 Chroma 目录、旧版 pkl 缓存，并清空 ``_KB_INDEX_MEMORY``。

    不修改 ``documents.csv``；重建索引请再执行 ``sync_system_kb``。
    """
    from agentic_rag.experiment import kb_index_builder as kb_mod

    root = (project_root or app_config.PROJECT_ROOT).resolve()
    report: dict[str, Any] = {"ok": True, "removed": []}

    persist = Path(app_config.CHROMA_PERSIST_DIRECTORY or "").expanduser()
    if persist.is_dir():
        shutil.rmtree(persist)
        report["removed"].append(str(persist))
    persist.mkdir(parents=True, exist_ok=True)

    legacy_pkl = root / "data" / "processed" / ".kb_embedding_cache.pkl"
    if legacy_pkl.is_file():
        legacy_pkl.unlink()
        report["removed"].append(str(legacy_pkl))

    if remove_chunks_jsonl:
        chunks = root / "data" / "processed" / "chunks.jsonl"
        if chunks.is_file():
            chunks.unlink()
            report["removed"].append(str(chunks))

    kb_mod._KB_INDEX_MEMORY.clear()
    kb_mod._KB_CHROMA_HIT_PRINTED.clear()
    report["chroma_persist_directory"] = str(persist)
    return report
