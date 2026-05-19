"""
会话级临时向量索引：对用户附加文件切块 + embedding，**不**写入 documents.csv / 全库 Chroma。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentic_rag.ark.embeddings import embed_texts
from agentic_rag.experiment.kb_index_builder import load_document_text
from agentic_rag.rag.simple import SimpleVectorIndex, chunk_text

CHUNK_SIZE = 500
CHUNK_OVERLAP = 80


def build_ephemeral_session_index(
    file_paths: list[Path],
    *,
    session_label: str = "session",
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> tuple[SimpleVectorIndex | None, dict[str, Any]]:
    """
    将多个文件合并为一个内存 ``SimpleVectorIndex``（带 doc_id / chunk_id 元数据）。
    """
    if not file_paths:
        return None, {"ok": False, "error": "无文件"}

    all_chunks: list[str] = []
    meta_list: list[dict[str, Any]] = []
    sources: list[str] = []

    for fi, fp in enumerate(file_paths):
        fp = fp.resolve()
        if not fp.is_file():
            continue
        try:
            raw_text = load_document_text(fp)
        except Exception as exc:
            return None, {
                "ok": False,
                "error": f"无法读取 {fp}: {type(exc).__name__}: {exc}",
            }
        pseudo_doc = f"sess_{fi:03d}"
        doc_text = "\n".join(
            [
                f"Document ID: {pseudo_doc}",
                f"Title: {fp.stem}",
                f"Source Path: {fp}",
                "",
                raw_text,
            ]
        )
        parts = chunk_text(doc_text, chunk_size=chunk_size, overlap=chunk_overlap)
        for ci, chunk in enumerate(parts):
            all_chunks.append(chunk)
            meta_list.append(
                {
                    "chunk_id": f"{pseudo_doc}::chunk_{ci:04d}",
                    "doc_id": pseudo_doc,
                    "title": fp.stem,
                    "source": str(fp),
                    "chunk_index": ci,
                }
            )
        sources.append(str(fp))

    if not all_chunks:
        return None, {"ok": False, "error": "解析后无文本块"}

    vectors = embed_texts(all_chunks, is_query=False)
    index = SimpleVectorIndex(chunks=all_chunks, vectors=vectors)
    index.source = f"ephemeral:{session_label}"
    index.chunk_metadata = meta_list
    return index, {
        "ok": True,
        "file_count": len(sources),
        "chunk_count": len(all_chunks),
        "sources": sources,
    }
