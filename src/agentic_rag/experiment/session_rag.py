"""
会话临时索引上下文：供 ``topic4_rag_query`` 在「仅附加文件」或「全库+附加」时检索。
"""

from __future__ import annotations

import contextvars
import time
from pathlib import Path
from typing import Any

from agentic_rag import config as app_config
from agentic_rag.experiment.kb_index_builder import load_or_build_knowledge_index
from agentic_rag.experiment.profile import RunProfile, resolve_bm25_tokenizer
from agentic_rag.pipelines.local_rag import (
    _now_run_id,
    build_citations,
    generate_answer_from_hits,
    retrieve_merged_from_indexes,
    run_c0_with_index,
    run_c1_with_index,
)
from agentic_rag.rag.context_expand import expand_hits_with_neighbors
from agentic_rag.rag.simple import SimpleVectorIndex
from agentic_rag.rewrite import build_retrieval_queries, rewrite_query
from agentic_rag.schemas import EvidenceChunk, RewriteResult

_ephemeral_index: contextvars.ContextVar[SimpleVectorIndex | None] = contextvars.ContextVar(
    "topic4_ephemeral_session_index",
    default=None,
)
_combine_with_full_kb: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "topic4_combine_ephemeral_with_kb",
    default=False,
)


def set_ephemeral_session_index(index: SimpleVectorIndex | None) -> contextvars.Token:
    return _ephemeral_index.set(index)


def reset_ephemeral_session_index(token: contextvars.Token) -> None:
    _ephemeral_index.reset(token)


def get_ephemeral_session_index() -> SimpleVectorIndex | None:
    return _ephemeral_index.get()


def set_combine_ephemeral_with_kb(enabled: bool) -> contextvars.Token:
    return _combine_with_full_kb.set(bool(enabled))


def reset_combine_ephemeral_with_kb(token: contextvars.Token) -> None:
    _combine_with_full_kb.reset(token)


def get_combine_ephemeral_with_kb() -> bool:
    return bool(_combine_with_full_kb.get())


def _ephemeral_doc_ids(index: SimpleVectorIndex) -> frozenset[str]:
    meta = getattr(index, "chunk_metadata", None) or []
    ids: set[str] = set()
    for m in meta:
        if isinstance(m, dict):
            did = str(m.get("doc_id") or "").strip()
            if did:
                ids.add(did)
    return frozenset(ids)


def _expand_merged_hits(
    hits: list[EvidenceChunk],
    *,
    kb_index: SimpleVectorIndex,
    ephemeral_index: SimpleVectorIndex,
    neighbors: int,
) -> list[EvidenceChunk]:
    if neighbors <= 0 or not hits:
        return hits
    ep_ids = _ephemeral_doc_ids(ephemeral_index)
    kb_hits = [h for h in hits if h.doc_id not in ep_ids]
    ep_hits = [h for h in hits if h.doc_id in ep_ids]
    groups: list[list[EvidenceChunk]] = []
    if kb_hits:
        groups.append(
            expand_hits_with_neighbors(kb_hits, kb_index, neighbors=neighbors)
        )
    if ep_hits:
        groups.append(
            expand_hits_with_neighbors(ep_hits, ephemeral_index, neighbors=neighbors)
        )
    if not groups:
        return hits
    from agentic_rag.pipelines.local_rag import merge_evidence_hits

    return merge_evidence_hits(groups, top_k=len(hits))


def _profile_retrieval_kwargs(p: RunProfile) -> dict[str, Any]:
    tok = resolve_bm25_tokenizer(p.bm25_tokenizer)
    return {
        "top_k": p.top_k,
        "hybrid": p.use_hybrid_retrieval,
        "dense_weight": p.dense_weight,
        "bm25_weight": p.bm25_weight,
        "bm25_tokenize": tok,
        "use_rerank": p.use_rerank,
        "rerank_backend": p.rerank_backend,
        "rerank_pool_size": p.rerank_pool_size,
        "context_neighbor_chunks": p.context_neighbor_chunks,
        "log_dir": p.log_dir if p.save_jsonl_log else None,
        "prompt_file": p.rewrite_prompt_file,
    }


def run_ephemeral_session_rag(
    question: str,
    profile: RunProfile | None = None,
) -> dict[str, Any]:
    """在已设置的会话临时索引上执行 RAG（与全库 ``run_knowledge_base_rag`` 参数对齐）。"""
    index = get_ephemeral_session_index()
    if index is None:
        return {
            "answer": "",
            "error": "当前无会话临时索引（请先绑定附加文件并开始会话）",
            "config": "session_ephemeral",
        }
    p = profile or RunProfile()
    kw = _profile_retrieval_kwargs(p)
    log_dir = kw.pop("log_dir")
    prompt_file = kw.pop("prompt_file")
    if p.use_query_rewrite:
        result = run_c1_with_index(
            index,
            question,
            prompt_file=prompt_file,
            log_dir=log_dir,
            **kw,
        )
    else:
        result = run_c0_with_index(
            index,
            question,
            log_dir=log_dir,
            **kw,
        )
    result["config"] = "session_ephemeral"
    result["run_profile"] = p.to_dict()
    return result


def run_combined_kb_ephemeral_rag(
    question: str,
    profile: RunProfile | None = None,
    *,
    project_root: Path | None = None,
    allowed_doc_ids: list[str] | None = None,
) -> dict[str, Any]:
    """
    单次 RAG：Chroma 全库 + 本会话临时索引，检索结果按 chunk_id 融合后再生成答案。
    """
    ephemeral = get_ephemeral_session_index()
    if ephemeral is None:
        return {
            "answer": "",
            "error": "当前无会话临时索引（全库+附加模式需先绑定附加文件）",
            "config": "kb_and_session_ephemeral",
        }

    p = profile or RunProfile()
    root = (project_root or app_config.PROJECT_ROOT).resolve()
    documents_csv = root / "data" / "processed" / "documents.csv"
    chunks_jsonl = root / "data" / "processed" / "chunks.jsonl"
    if not documents_csv.is_file():
        return {
            "answer": "",
            "error": f"未找到知识库清单：{documents_csv}",
            "config": "kb_and_session_ephemeral",
            "run_profile": p.to_dict(),
        }

    kb_index = load_or_build_knowledge_index(
        root,
        documents_csv=documents_csv,
        chunks_jsonl=chunks_jsonl,
        use_cache=p.use_chroma_cache,
    )

    doc_filter: frozenset[str] | None = None
    if allowed_doc_ids:
        doc_filter = frozenset(str(x) for x in allowed_doc_ids if str(x).strip())

    kw = _profile_retrieval_kwargs(p)
    neighbors = int(kw.pop("context_neighbor_chunks"))
    kw.pop("prompt_file")
    log_dir = kw.pop("log_dir")

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
    ark_embedding_usage: dict[str, Any] = {}

    try:
        if p.use_query_rewrite:
            rewrite_result = rewrite_query(
                question, prompt_file=p.rewrite_prompt_file
            )
            retrieval_queries = build_retrieval_queries(question, rewrite_result)

        hits, rerank_usage, ark_embedding_usage = retrieve_merged_from_indexes(
            [kb_index, ephemeral],
            retrieval_queries,
            allowed_doc_ids=doc_filter,
            rerank=kw.pop("use_rerank"),
            **kw,
        )
        hits = _expand_merged_hits(
            hits,
            kb_index=kb_index,
            ephemeral_index=ephemeral,
            neighbors=neighbors,
        )
        answer, answer_usage = generate_answer_from_hits(question, hits)
    except Exception as exc:
        error = str(exc)

    latency_ms = int((time.perf_counter() - started) * 1000)
    config_name = (
        "kb_and_session_ephemeral_c1"
        if p.use_query_rewrite
        else "kb_and_session_ephemeral"
    )
    result: dict[str, Any] = {
        "run_id": _now_run_id("kb_ep"),
        "config": config_name,
        "question_id": p.question_id,
        "original_query": question,
        "retrieval_queries": retrieval_queries,
        "retrieved_chunks": [hit.to_dict() for hit in hits],
        "answer": answer,
        "citations": build_citations(hits),
        "latency_ms": latency_ms,
        "token_usage": {
            "ark_volcengine_embedding": ark_embedding_usage,
            "query_rewrite": rewrite_result.token_usage
            if p.use_query_rewrite
            else {},
            "rerank": rerank_usage,
            "answer_generation": answer_usage,
        },
        "token_cost": None,
        "error": error,
        "log_path": "",
        "retrieval_scope": "full_kb_and_ephemeral",
        "run_profile": p.to_dict(),
    }
    if p.use_query_rewrite:
        result.update(
            {
                "need_rewrite": rewrite_result.need_rewrite,
                "rewrite_confidence": rewrite_result.rewrite_confidence,
                "rewrite_reason": rewrite_result.rewrite_reason,
                "rewrite_type": rewrite_result.rewrite_type,
                "rewritten_query": rewrite_result.rewritten_query,
                "rewritten_queries": rewrite_result.rewritten_queries,
                "query_rewrite_model_raw": rewrite_result.raw_output,
            }
        )
    if log_dir is not None:
        from agentic_rag.logging_utils import append_run_log

        result["log_path"] = append_run_log(result, log_dir)
    return result
