"""
知识库向量索引：构建切块并 embedding。

首次运行会调用方舟 API，耗时较长；成功后写入 ``data/processed/.kb_embedding_cache.pkl``，
在 ``documents.csv`` 与源文件指纹未变时可跳过 embedding，避免再次卡在批量向量请求上。
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
from agentic_rag.rag.simple import SimpleVectorIndex, chunk_text


TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".csv", ".py"}
CHUNK_SIZE = 500
CHUNK_OVERLAP = 80


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


def _cache_path(project_root: Path) -> Path:
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
    cache_file = _cache_path(project_root)

    if use_cache and not force_rebuild and cache_file.is_file():
        try:
            with cache_file.open("rb") as f:
                blob = pickle.load(f)
            if (
                isinstance(blob, dict)
                and blob.get("fingerprint") == fp_expected
                and blob.get("chunks")
                and blob.get("vectors")
            ):
                print(
                    f"[index] 使用本地向量缓存（命中指纹 {fp_expected[:12]}…），跳过方舟 embedding。"
                )
                index = SimpleVectorIndex(
                    chunks=blob["chunks"], vectors=blob["vectors"]
                )
                index.doc_id = "knowledge_base"
                index.source = str(documents_csv)
                index.chunk_metadata = blob.get("metadata") or []
                return index
        except (pickle.PickleError, OSError, KeyError) as exc:
            print(f"[index] 缓存读取失败，将重新 embedding：{exc}")

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
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with cache_file.open("wb") as f:
            pickle.dump(
                {
                    "fingerprint": fp_expected,
                    "chunks": chunks,
                    "vectors": vectors,
                    "metadata": metadata,
                },
                f,
                protocol=pickle.HIGHEST_PROTOCOL,
            )
        print(f"[index] 已写入向量缓存：{cache_file}")
    except OSError as exc:
        print(f"[WARN] 无法写入向量缓存（下次仍将全量 embedding）：{exc}")

    return index
