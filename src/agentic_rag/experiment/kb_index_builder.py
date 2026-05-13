"""
知识库向量索引：构建切块并 embedding。

向量持久化使用 **Chroma**（集合名由 ``kb_fingerprint`` 决定，前缀 ``ragkb_kb_``），与单文档 RAG 共用
``CHROMA_PERSIST_DIRECTORY``。若检测到旧版 ``data/processed/.kb_embedding_cache.pkl`` 且指纹一致，
会自动迁移到 Chroma 并删除该 pkl。
"""

from __future__ import annotations

import hashlib
import json
import pickle
from pathlib import Path
from typing import Any

from agentic_rag import config
from agentic_rag.ark.embeddings import embed_texts
from agentic_rag.documents import parse_path
from agentic_rag.rag.chroma_store import (
    kb_collection_name,
    persist_kb_index,
    try_load_kb_index,
)
from agentic_rag.rag.simple import SimpleVectorIndex, chunk_text


TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".csv", ".py"}
CHUNK_SIZE = 500
CHUNK_OVERLAP = 80

# 同一进程内多次 topic4_rag_query 会重复加载索引；缓存命中日志只打一次，避免刷屏与终端混杂。
_KB_CHROMA_HIT_PRINTED: set[str] = set()
# 内存级缓存：同一 fingerprint 只从 Chroma 还原一次 SimpleVectorIndex，后续工具调用直接复用。
_KB_INDEX_MEMORY: dict[str, SimpleVectorIndex] = {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    import csv

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8-sig", errors="replace")


def load_document_text(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return read_text_file(file_path)
    return parse_path(file_path).text


def kb_fingerprint(
    documents_csv: Path,
    project_root: Path,
    *,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> str:
    """知识库内容指纹：documents.csv + 各行指向文件的 mtime/size + 切块与模型参数。"""
    rows = read_csv_rows(documents_csv)
    parts: list[str] = []
    for row in sorted(rows, key=lambda r: r.get("doc_id", "")):
        rel = row.get("file_path", "")
        fp = (project_root / rel).resolve()
        if fp.is_file():
            st = fp.stat()
            parts.append(f"{rel}:{st.st_mtime_ns}:{st.st_size}")
        else:
            parts.append(f"{rel}:missing")
    meta = "|".join(parts)
    model = config.ARK_EMBEDDING_MODEL or ""
    dim = str(config.ARK_EMBEDDING_DIMENSIONS)
    raw = (
        f"{meta}|csv={documents_csv.stat().st_mtime_ns}|"
        f"m={model}|d={dim}|cs={chunk_size}|ov={chunk_overlap}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def collect_kb_chunks(
    project_root: Path,
    documents_csv: Path,
    chunks_jsonl: Path,
    *,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> tuple[list[str], list[dict[str, Any]]]:
    documents = read_csv_rows(documents_csv)
    chunks: list[str] = []
    metadata: list[dict[str, Any]] = []

    for row in documents:
        file_path = (project_root / row["file_path"]).resolve()
        if not file_path.is_file():
            print(f"[WARN] skip missing document: {row['file_path']}")
            continue

        raw_text = load_document_text(file_path)
        doc_text = "\n".join(
            [
                f"Document ID: {row['doc_id']}",
                f"Title: {row.get('title', '')}",
                f"Document Type: {row.get('doc_type', '')}",
                f"Source Note: {row.get('source', '')}",
                "",
                raw_text,
            ]
        )
        doc_chunks = chunk_text(doc_text, chunk_size=chunk_size, overlap=chunk_overlap)
        for chunk_index, chunk in enumerate(doc_chunks):
            chunks.append(chunk)
            metadata.append(
                {
                    "chunk_id": f"{row['doc_id']}::chunk_{chunk_index:04d}",
                    "doc_id": row["doc_id"],
                    "title": row.get("title", ""),
                    "source": str(file_path),
                    "relative_path": row["file_path"],
                    "doc_type": row.get("doc_type", ""),
                    "chunk_index": chunk_index,
                    "page": None,
                }
            )

    if not chunks:
        raise ValueError("No document chunks were built from documents.csv")

    chunks_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with chunks_jsonl.open("w", encoding="utf-8") as f:
        for chunk, meta in zip(chunks, metadata, strict=True):
            f.write(
                json.dumps({**meta, "text": chunk}, ensure_ascii=False) + "\n"
            )

    return chunks, metadata


def _legacy_cache_path(project_root: Path) -> Path:
    return project_root / "data" / "processed" / ".kb_embedding_cache.pkl"


def load_or_build_knowledge_index(
    project_root: Path,
    *,
    documents_csv: Path,
    chunks_jsonl: Path,
    use_cache: bool = True,
    force_rebuild: bool = False,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> SimpleVectorIndex:
    fp_expected = kb_fingerprint(
        documents_csv,
        project_root,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    if force_rebuild:
        _KB_INDEX_MEMORY.pop(fp_expected, None)

    if (
        use_cache
        and not force_rebuild
        and fp_expected in _KB_INDEX_MEMORY
    ):
        mem = _KB_INDEX_MEMORY[fp_expected]
        mem.doc_id = "knowledge_base"
        mem.source = str(documents_csv)
        return mem

    if use_cache and not force_rebuild:
        try:
            cached = try_load_kb_index(fp_expected)
            if cached is not None:
                cached.doc_id = "knowledge_base"
                cached.source = str(documents_csv)
                coll = kb_collection_name(fp_expected)
                if coll not in _KB_CHROMA_HIT_PRINTED:
                    _KB_CHROMA_HIT_PRINTED.add(coll)
                    print(f"[index] 使用 Chroma 知识库集合 `{coll}`，跳过 embedding。")
                _KB_INDEX_MEMORY[fp_expected] = cached
                return cached
        except Exception as exc:
            print(f"[index] Chroma 读取失败，将尝试旧缓存或重建：{exc}")

        legacy = _legacy_cache_path(project_root)
        if legacy.is_file():
            try:
                with legacy.open("rb") as f:
                    blob = pickle.load(f)
                if (
                    isinstance(blob, dict)
                    and blob.get("fingerprint") == fp_expected
                    and blob.get("chunks")
                    and blob.get("vectors")
                ):
                    index = SimpleVectorIndex(
                        chunks=blob["chunks"], vectors=blob["vectors"]
                    )
                    index.doc_id = "knowledge_base"
                    index.source = str(documents_csv)
                    index.chunk_metadata = blob.get("metadata") or []
                    persist_kb_index(fp_expected, index)
                    print(
                        f"[index] 已从旧版 .pkl 迁移至 Chroma：`{kb_collection_name(fp_expected)}`"
                    )
                    try:
                        legacy.unlink()
                        print("[index] 已删除旧版 .kb_embedding_cache.pkl")
                    except OSError as exc:
                        print(f"[WARN] 无法删除旧 pkl：{exc}")
                    _KB_INDEX_MEMORY[fp_expected] = index
                    return index
            except (pickle.PickleError, OSError, KeyError, TypeError) as exc:
                print(f"[index] 旧版 pkl 不可用：{exc}")

    print(
        "[index] 首次构建或无有效缓存：正在切块并调用方舟 embedding（chunk 多时可能需数分钟，请勿中断）…"
    )
    chunks, metadata = collect_kb_chunks(
        project_root,
        documents_csv,
        chunks_jsonl,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    print(f"[index] 共 {len(chunks)} 个文本块，开始向量化…")
    vectors = embed_texts(chunks, is_query=False)
    index = SimpleVectorIndex(chunks=chunks, vectors=vectors)
    index.doc_id = "knowledge_base"
    index.source = str(documents_csv)
    index.chunk_metadata = metadata

    try:
        persist_kb_index(fp_expected, index)
        print(
            f"[index] 已向量化并写入 Chroma：`{kb_collection_name(fp_expected)}` "
            f"（持久化目录见 CHROMA_PERSIST_DIRECTORY）"
        )
    except Exception as exc:
        print(f"[WARN] 无法写入 Chroma（下次仍将全量 embedding）：{exc}")

    _KB_INDEX_MEMORY[fp_expected] = index
    return index
