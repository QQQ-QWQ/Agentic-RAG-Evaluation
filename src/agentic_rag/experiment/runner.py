"""统一实验入口：按 RunProfile 组装索引与 C0/C1 管线。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentic_rag.experiment.profile import RunProfile, resolve_bm25_tokenizer
from agentic_rag.pipelines.local_rag import (
    build_vector_index,
    run_c0_with_index,
    run_c1_with_index,
)


def run_document_rag(
    doc_path: str | Path,
    question: str,
    profile: RunProfile | None = None,
) -> dict[str, Any]:
    """
    单文档 RAG：默认 Chroma + 混合检索 + C1 rewrite。

    新能力在 ``pipelines`` / ``rag`` 等实现后于此接线；CLI 见根目录 ``main.py rag``。
    """
    p = profile or RunProfile()
    index = build_vector_index(doc_path, use_chroma=p.use_chroma_cache)

    tok = resolve_bm25_tokenizer(p.bm25_tokenizer)
    hybrid = p.use_hybrid_retrieval
    log_dir = p.log_dir if p.save_jsonl_log else None

    common_kwargs: dict[str, Any] = {
        "top_k": p.top_k,
        "question_id": p.question_id,
        "hybrid": hybrid,
        "dense_weight": p.dense_weight,
        "bm25_weight": p.bm25_weight,
        "bm25_tokenize": tok,
        "log_dir": log_dir,
        "use_rerank": p.use_rerank,
        "rerank_backend": p.rerank_backend,
        "rerank_pool_size": p.rerank_pool_size,
        "context_neighbor_chunks": p.context_neighbor_chunks,
    }

    if p.use_query_rewrite:
        result = run_c1_with_index(
            index,
            question,
            prompt_file=p.rewrite_prompt_file,
            **common_kwargs,
        )
    else:
        result = run_c0_with_index(index, question, **common_kwargs)

    result["run_profile"] = p.to_dict()
    return result
