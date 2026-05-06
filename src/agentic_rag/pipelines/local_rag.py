"""
本地文件 RAG：解析 → 分块 → 方舟向量 → 余弦检索 → DeepSeek 生成。
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from pathlib import Path

from agentic_rag import config
from agentic_rag.ark.embeddings import embed_texts
from agentic_rag.documents import parse_path
from agentic_rag.logging_utils import append_run_log
from agentic_rag.llm.deepseek import create_deepseek_client
from agentic_rag.rewrite import build_retrieval_queries, rewrite_query
from agentic_rag.schemas import EvidenceChunk, RewriteResult
from agentic_rag.rag.bm25 import BM25Index, chinese_bigram_tokenize
from agentic_rag.rag.chroma_store import persist_index, try_load_index
from agentic_rag.rag.context_expand import expand_hits_with_neighbors
from agentic_rag.rag.fusion import fuse_dense_bm25
from agentic_rag.rag.rerank import rerank_hits
from agentic_rag.rag.simple import SimpleVectorIndex, chunk_text, cosine_sim


def _cached_bm25_index(
    index: SimpleVectorIndex,
    tokenize: Callable[[str], list[str]],
) -> BM25Index:
    """同一索引缓存 BM25，避免每条检索查询重复建树。"""
    tag = getattr(tokenize, "__name__", repr(tokenize))
    cur = getattr(index, "_bm25_tokenize_tag", None)
    cached = getattr(index, "_bm25_index_cached", None)
    if cached is None or cur != tag:
        index._bm25_index_cached = BM25Index(index.chunks, tokenize=tokenize)
        index._bm25_tokenize_tag = tag
    return index._bm25_index_cached


def build_vector_index(
    doc_path: str | Path,
    *,
    use_chroma: bool = True,
) -> SimpleVectorIndex:
    """
    解析文档、切块并向量化，返回内存索引（可多次用于问答）。

    ``use_chroma=True``（默认）：Chroma 命中则加载；新建后持久化。
    ``use_chroma=False``：不读写磁盘（便于对照或调试）。
    """
    path = Path(doc_path).expanduser().resolve()
    if use_chroma:
        cached = try_load_index(path)
        if cached is not None:
            return cached

    doc = parse_path(path)
    chunks = chunk_text(doc.text)
    if not chunks:
        raise ValueError("文档解析后无文本，无法建索引")
    vectors = embed_texts(chunks, is_query=False)
    index = SimpleVectorIndex(chunks=chunks, vectors=vectors)
    index.doc_id = Path(doc.path).stem
    index.source = doc.path
    index.chunk_metadata = [
        {
            "chunk_id": f"{index.doc_id}::chunk_{i:04d}",
            "doc_id": index.doc_id,
            "source": doc.path,
            "page": None,
        }
        for i in range(len(chunks))
    ]
    if use_chroma:
        persist_index(path, index)
    return index


def answer_with_index(
    index: SimpleVectorIndex,
    question: str,
    *,
    top_k: int = 4,
    system_prompt: str | None = None,
) -> str:
    """在已有索引上检索并调用 DeepSeek 生成回答。"""
    qv = embed_texts([question], is_query=True)[0]
    hits = index.top_k(qv, k=top_k)
    context = "\n\n---\n\n".join(h for h, _ in hits)

    sys_msg = system_prompt or (
        "你是课程助手。请只根据「参考片段」作答；不够就说不知道，不要编造。"
    )

    client = create_deepseek_client()
    resp = client.chat.completions.create(
        model=config.DEEPSEEK_CHAT_MODEL or "deepseek-chat",
        messages=[
            {"role": "system", "content": sys_msg},
            {
                "role": "user",
                "content": f"参考片段：\n{context}\n\n问题：{question}",
            },
        ],
    )
    return (resp.choices[0].message.content or "").strip()


def local_rag_answer(
    doc_path: str | Path,
    question: str,
    *,
    top_k: int = 4,
    system_prompt: str | None = None,
    use_chroma: bool = True,
) -> str:
    """
    对单个本地文档做检索增强问答。
    Chroma 已缓存同一文档时不再重复向量化文档块（``use_chroma=True`` 时）。
    需要环境变量：ARK_*（向量）、DEEPSEEK_*（生成）；目录见 CHROMA_PERSIST_DIRECTORY。
    """
    index = build_vector_index(doc_path, use_chroma=use_chroma)
    return answer_with_index(
        index, question, top_k=top_k, system_prompt=system_prompt
    )


def _now_run_id(prefix: str) -> str:
    return f"{prefix}-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}"


def _merge_hits(hit_groups: list[list[EvidenceChunk]], top_k: int) -> list[EvidenceChunk]:
    best: dict[str, EvidenceChunk] = {}
    for hits in hit_groups:
        for hit in hits:
            current = best.get(hit.chunk_id)
            if current is None or hit.score > current.score:
                best[hit.chunk_id] = hit
    merged = sorted(best.values(), key=lambda item: item.score, reverse=True)[:top_k]
    return [
        EvidenceChunk(
            chunk_id=hit.chunk_id,
            doc_id=hit.doc_id,
            text=hit.text,
            score=hit.score,
            source=hit.source,
            page=hit.page,
            rank=i + 1,
            query=hit.query,
        )
        for i, hit in enumerate(merged)
    ]


def retrieve_with_index(
    index: SimpleVectorIndex,
    queries: list[str],
    *,
    top_k: int = 5,
    hybrid: bool = True,
    dense_weight: float = 0.6,
    bm25_weight: float = 0.4,
    bm25_tokenize: Callable[[str], list[str]] | None = None,
    rerank: bool = False,
    rerank_backend: str = "llm",
    rerank_pool_size: int = 20,
) -> tuple[list[EvidenceChunk], dict[str, int]]:
    """
    检索：默认 **混合检索**（稠密余弦 + BM25），两路分数分别 min-max 归一化后按权重加权求和。

    ``bm25_tokenize`` 默认 ``chinese_bigram_tokenize``（中文友好、无额外依赖）。
    设为 ``hybrid=False`` 则退化为纯向量检索。

    ``rerank=True`` 时先在 ``rerank_pool_size`` 规模的粗检候选上调用 ``rerank_hits``（见 ``rerank_backend``），
    再保留 ``top_k``；返回的第二项为各子查询重排 token 用量之和。
    """
    hit_groups: list[list[EvidenceChunk]] = []
    rerank_usage_total: dict[str, int] = {}
    doc_id = str(getattr(index, "doc_id", "doc_001"))
    source = str(getattr(index, "source", ""))
    chunk_metadata = getattr(index, "chunk_metadata", None)
    tokenize = bm25_tokenize or chinese_bigram_tokenize
    for query in queries:
        query_text = query.strip()
        if not query_text:
            continue
        qv = embed_texts([query_text], is_query=True)[0]
        dense_scores = [
            cosine_sim(qv, vector) for vector in index.vectors
        ]
        if (
            hybrid
            and index.chunks
            and len(dense_scores) == len(index.chunks)
        ):
            bm25_index = _cached_bm25_index(index, tokenize)
            bm25_scores = bm25_index.scores(query_text)
            scores = fuse_dense_bm25(
                dense_scores,
                bm25_scores,
                dense_weight=dense_weight,
                bm25_weight=bm25_weight,
            )
        else:
            scores = dense_scores
        scored: list[EvidenceChunk] = []
        for i, chunk in enumerate(index.chunks):
            meta = (
                chunk_metadata[i]
                if isinstance(chunk_metadata, list) and i < len(chunk_metadata)
                else {}
            )
            hit_doc_id = str(meta.get("doc_id") or doc_id)
            hit_source = str(meta.get("source") or source)
            hit_chunk_id = str(
                meta.get("chunk_id") or f"{hit_doc_id}::chunk_{i:04d}"
            )
            page = meta.get("page")
            scored.append(
                EvidenceChunk(
                    chunk_id=hit_chunk_id,
                    doc_id=hit_doc_id,
                    text=chunk,
                    score=scores[i],
                    source=hit_source,
                    page=page if isinstance(page, int) else None,
                    rank=i + 1,
                    query=query_text,
                )
            )
        scored.sort(key=lambda item: item.score, reverse=True)
        if rerank:
            pool_cap = max(top_k, min(rerank_pool_size, len(scored)))
            pool = scored[:pool_cap]
            pool, usage = rerank_hits(
                query_text,
                pool,
                top_k=top_k,
                backend=rerank_backend,
            )
            for key, val in usage.items():
                rerank_usage_total[key] = rerank_usage_total.get(key, 0) + val
        else:
            pool = scored[:top_k]
        hit_groups.append(pool)
    merged = _merge_hits(hit_groups, top_k=top_k)
    return merged, rerank_usage_total


def _usage_to_dict(usage) -> dict[str, int]:
    if usage is None:
        return {}
    out: dict[str, int] = {}
    for attr in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = getattr(usage, attr, None)
        if value is not None:
            out[attr] = int(value)
    return out


def generate_answer_from_hits(
    question: str,
    hits: list[EvidenceChunk],
    *,
    system_prompt: str | None = None,
) -> tuple[str, dict[str, int]]:
    context = "\n\n---\n\n".join(
        f"[{hit.chunk_id}] {hit.text}" for hit in hits
    )
    sys_msg = system_prompt or (
        "You are a course and knowledge-service RAG assistant. Answer only from the "
        "provided evidence. If the evidence is insufficient, say so clearly. Include "
        "chunk ids when citing evidence."
    )
    client = create_deepseek_client()
    resp = client.chat.completions.create(
        model=config.DEEPSEEK_CHAT_MODEL or "deepseek-chat",
        messages=[
            {"role": "system", "content": sys_msg},
            {
                "role": "user",
                "content": f"Evidence:\n{context}\n\nQuestion:\n{question}",
            },
        ],
    )
    answer = (resp.choices[0].message.content or "").strip()
    return answer, _usage_to_dict(getattr(resp, "usage", None))


def build_citations(hits: list[EvidenceChunk]) -> list[dict[str, str]]:
    return [{"doc_id": hit.doc_id, "chunk_id": hit.chunk_id} for hit in hits]


def run_c0_with_index(
    index: SimpleVectorIndex,
    question: str,
    *,
    question_id: str = "",
    top_k: int = 5,
    system_prompt: str | None = None,
    log_dir: str | Path | None = None,
    hybrid: bool = True,
    dense_weight: float = 0.6,
    bm25_weight: float = 0.4,
    bm25_tokenize: Callable[[str], list[str]] | None = None,
    use_rerank: bool = False,
    rerank_backend: str = "llm",
    rerank_pool_size: int = 20,
    context_neighbor_chunks: int = 0,
) -> dict:
    started = time.perf_counter()
    error = ""
    hits: list[EvidenceChunk] = []
    answer = ""
    answer_usage: dict[str, int] = {}
    rerank_usage: dict[str, int] = {}
    try:
        hits, rerank_usage = retrieve_with_index(
            index,
            [question],
            top_k=top_k,
            hybrid=hybrid,
            dense_weight=dense_weight,
            bm25_weight=bm25_weight,
            bm25_tokenize=bm25_tokenize,
            rerank=use_rerank,
            rerank_backend=rerank_backend,
            rerank_pool_size=rerank_pool_size,
        )
        hits = expand_hits_with_neighbors(
            hits,
            index,
            neighbors=context_neighbor_chunks,
        )
        answer, answer_usage = generate_answer_from_hits(
            question,
            hits,
            system_prompt=system_prompt,
        )
    except Exception as exc:
        error = str(exc)
    latency_ms = int((time.perf_counter() - started) * 1000)
    result = {
        "run_id": _now_run_id("c0"),
        "config": "c0_naive",
        "question_id": question_id,
        "original_query": question,
        "retrieval_queries": [question],
        "retrieved_chunks": [hit.to_dict() for hit in hits],
        "answer": answer,
        "citations": build_citations(hits),
        "latency_ms": latency_ms,
        "token_usage": {
            "rerank": rerank_usage,
            "answer_generation": answer_usage,
        },
        "token_cost": None,
        "error": error,
        "log_path": "",
    }
    if log_dir is not None:
        result["log_path"] = append_run_log(result, log_dir)
    return result


def run_c1_with_index(
    index: SimpleVectorIndex,
    question: str,
    *,
    question_id: str = "",
    top_k: int = 5,
    prompt_file: str | Path | None = None,
    system_prompt: str | None = None,
    log_dir: str | Path | None = None,
    hybrid: bool = True,
    dense_weight: float = 0.6,
    bm25_weight: float = 0.4,
    bm25_tokenize: Callable[[str], list[str]] | None = None,
    use_rerank: bool = False,
    rerank_backend: str = "llm",
    rerank_pool_size: int = 20,
    context_neighbor_chunks: int = 0,
) -> dict:
    started = time.perf_counter()
    error = ""
    rewrite_result = RewriteResult(
        need_rewrite=False,
        rewrite_reason="not executed",
        rewritten_query=question,
    )
    retrieval_queries = [question]
    hits: list[EvidenceChunk] = []
    answer = ""
    answer_usage: dict[str, int] = {}
    rerank_usage: dict[str, int] = {}
    try:
        rewrite_result = rewrite_query(question, prompt_file=prompt_file)
        retrieval_queries = build_retrieval_queries(question, rewrite_result)
        hits, rerank_usage = retrieve_with_index(
            index,
            retrieval_queries,
            top_k=top_k,
            hybrid=hybrid,
            dense_weight=dense_weight,
            bm25_weight=bm25_weight,
            bm25_tokenize=bm25_tokenize,
            rerank=use_rerank,
            rerank_backend=rerank_backend,
            rerank_pool_size=rerank_pool_size,
        )
        hits = expand_hits_with_neighbors(
            hits,
            index,
            neighbors=context_neighbor_chunks,
        )
        answer, answer_usage = generate_answer_from_hits(
            question,
            hits,
            system_prompt=system_prompt,
        )
    except Exception as exc:
        error = str(exc)
    latency_ms = int((time.perf_counter() - started) * 1000)
    result = {
        "run_id": _now_run_id("c1"),
        "config": "c1_rewrite",
        "question_id": question_id,
        "original_query": question,
        "need_rewrite": rewrite_result.need_rewrite,
        "rewrite_reason": rewrite_result.rewrite_reason,
        "rewrite_type": rewrite_result.rewrite_type,
        "rewritten_query": rewrite_result.rewritten_query,
        "retrieval_queries": retrieval_queries,
        "retrieved_chunks": [hit.to_dict() for hit in hits],
        "answer": answer,
        "citations": build_citations(hits),
        "latency_ms": latency_ms,
        "token_usage": {
            "query_rewrite": rewrite_result.token_usage,
            "rerank": rerank_usage,
            "answer_generation": answer_usage,
        },
        "token_cost": None,
        "error": error,
        "log_path": "",
    }
    if log_dir is not None:
        result["log_path"] = append_run_log(result, log_dir)
    return result
