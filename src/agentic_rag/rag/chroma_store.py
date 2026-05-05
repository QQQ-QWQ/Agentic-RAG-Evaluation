"""Chroma 持久化：同一文档（路径 + 修改时间 + 大小）仅向量化一次，其余从磁盘加载索引。"""

from __future__ import annotations

import hashlib
from pathlib import Path

import chromadb

from agentic_rag import config
from agentic_rag.rag.simple import SimpleVectorIndex


def _identity_key(path: Path) -> str:
    p = path.expanduser().resolve()
    st = p.stat()
    raw = f"{p}:{st.st_mtime_ns}:{st.st_size}".encode()
    return hashlib.sha256(raw).hexdigest()


def _collection_name(identity_key: str) -> str:
    # Chroma：名称 3–512，来自 [a-zA-Z0-9._-]，且首尾为字母或数字
    return f"ragkb_{identity_key}"


def _numpy_embeddings_to_lists(embeddings: object) -> list[list[float]]:
    """兼容 numpy ndarray / list。"""
    if embeddings is None:
        return []
    try:
        import numpy as np

        if isinstance(embeddings, np.ndarray):
            return [row.astype("float64").tolist() for row in embeddings]
    except ImportError:
        pass
    out: list[list[float]] = []
    for row in embeddings:
        if hasattr(row, "tolist"):
            out.append([float(x) for x in row.tolist()])
        else:
            out.append([float(x) for x in row])
    return out


_chroma_client: chromadb.ClientAPI | None = None


def _client() -> chromadb.ClientAPI:
    global _chroma_client
    if _chroma_client is None:
        persist = config.CHROMA_PERSIST_DIRECTORY
        if not persist:
            raise ValueError("请配置 CHROMA_PERSIST_DIRECTORY")
        Path(persist).mkdir(parents=True, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=str(persist))
    return _chroma_client


def _collection_exists(client: chromadb.ClientAPI, name: str) -> bool:
    try:
        client.get_collection(name)
        return True
    except Exception:
        return False


def try_load_index(doc_path: Path) -> SimpleVectorIndex | None:
    """若 Chroma 中存在与当前配置一致的缓存则还原 SimpleVectorIndex，否则返回 None。"""
    path = doc_path.expanduser().resolve()
    if not path.is_file():
        return None

    identity = _identity_key(path)
    name = _collection_name(identity)
    client = _client()

    if not _collection_exists(client, name):
        return None

    coll = client.get_collection(name)
    if coll.count() == 0:
        return None

    data = coll.get(include=["embeddings", "documents", "metadatas"])
    docs = data.get("documents") or []
    emb_raw = data.get("embeddings")
    metas = data.get("metadatas") or []

    if not docs or emb_raw is None:
        client.delete_collection(name)
        return None

    vectors = _numpy_embeddings_to_lists(emb_raw)
    if len(docs) != len(vectors) or len(metas) != len(docs):
        client.delete_collection(name)
        return None

    model_now = config.ARK_EMBEDDING_MODEL or ""
    dim_now = config.ARK_EMBEDDING_DIMENSIONS

    rows: list[tuple[int, str, list[float]]] = []
    for i, (doc, vec, meta) in enumerate(zip(docs, vectors, metas, strict=True)):
        if meta is None:
            client.delete_collection(name)
            return None
        if meta.get("embedding_model") != model_now:
            client.delete_collection(name)
            return None
        if int(meta.get("embedding_dim", -1)) != dim_now:
            client.delete_collection(name)
            return None
        idx = int(meta.get("chunk_idx", i))
        rows.append((idx, doc, vec))

    rows.sort(key=lambda x: x[0])
    chunks = [r[1] for r in rows]
    vecs = [r[2] for r in rows]
    return SimpleVectorIndex(chunks=chunks, vectors=vecs)


def persist_index(doc_path: Path, index: SimpleVectorIndex) -> None:
    """将向量化结果写入 Chroma（覆盖同名集合）。"""
    path = doc_path.expanduser().resolve()
    identity = _identity_key(path)
    name = _collection_name(identity)
    client = _client()

    if _collection_exists(client, name):
        client.delete_collection(name)

    n = len(index.chunks)
    if n == 0:
        return

    coll = client.create_collection(name)
    model = config.ARK_EMBEDDING_MODEL or ""
    dim = config.ARK_EMBEDDING_DIMENSIONS
    metadatas = [
        {
            "chunk_idx": i,
            "embedding_model": model,
            "embedding_dim": dim,
        }
        for i in range(n)
    ]

    coll.add(
        ids=[f"ch_{i}" for i in range(n)],
        embeddings=index.vectors,
        documents=index.chunks,
        metadatas=metadatas,
    )
