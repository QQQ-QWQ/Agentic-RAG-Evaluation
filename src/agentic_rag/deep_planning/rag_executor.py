"""Execute fixed Topic4 RAG pipelines for RAG sub-agent tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentic_rag.deep_planning.presets import run_profile_for_preset
from agentic_rag.experiment.runner import run_document_rag, run_knowledge_base_rag
from agentic_rag.telemetry.audit_log import audit_record
from agentic_rag.telemetry.audit_payload import rag_result_to_payload, safe_json_obj


def _compact_subagent_result(
    raw: dict[str, Any],
    *,
    pipeline: str,
    max_chunks: int = 8,
    max_text_chars: int = 500,
) -> str:
    """Return compact JSON for the lead Agent without changing pipeline outputs."""
    chunks: list[dict[str, Any]] = []
    for ch in (raw.get("retrieved_chunks") or [])[:max_chunks]:
        if not isinstance(ch, dict):
            continue
        chunks.append(
            {
                "doc_id": ch.get("doc_id"),
                "chunk_id": ch.get("chunk_id"),
                "score": ch.get("score"),
                "text_preview": str(ch.get("text") or "")[:max_text_chars],
            }
        )
    kept_ids = {str(x) for x in (raw.get("evidence_grader_kept_chunk_ids") or [])}
    kept_chunks = [
        ch
        for ch in chunks
        if str(ch.get("chunk_id") or "") in kept_ids
    ] if kept_ids else chunks
    payload = {
        "pipeline": pipeline,
        "answer": raw.get("answer", ""),
        "error": raw.get("error", ""),
        "retrieval_queries": raw.get("retrieval_queries") or [],
        "sub_queries": raw.get("sub_queries") or raw.get("retrieval_queries") or [],
        "retrieved_chunks": chunks,
        "retrieved_chunk_ids": raw.get("retrieved_chunk_ids") or [],
        "expanded_chunk_ids": raw.get("expanded_chunk_ids") or [],
        "multi_query_fusion": raw.get("multi_query_fusion"),
        "rrf_input_count": raw.get("rrf_input_count"),
        "rrf_output_chunk_ids": raw.get("rrf_output_chunk_ids") or [],
        "evidence_grader_kept_chunk_ids": raw.get("evidence_grader_kept_chunk_ids") or [],
        "kept_evidence_chunks": kept_chunks,
        "evidence_grades": raw.get("evidence_grades") or [],
        "citations": raw.get("citations") or [],
        "final_citation_chunk_ids": raw.get("final_citation_chunk_ids") or [],
        "latency_ms": raw.get("latency_ms"),
    }
    return json.dumps(safe_json_obj(payload, max_len=16_000), ensure_ascii=False)


def execute_topic4_rag(
    question: str,
    pipeline_id: str,
    *,
    doc_path: str | Path | None = None,
    use_knowledge_base: bool | None = None,
    kb_doc_ids: list[str] | None = None,
    compact_max_chars: int = 12_000,
    evidence_max_chars: int = 6000,
    via_subagent: bool = False,
) -> str:
    """Execute one fixed RAG preset and return compact JSON for a LangChain tool."""
    del compact_max_chars, evidence_max_chars, via_subagent
    q = (question or "").strip()
    pipeline = (pipeline_id or "project_default").strip().lower()
    profile = run_profile_for_preset(pipeline)

    use_kb = doc_path is None if use_knowledge_base is None else use_knowledge_base
    if use_kb:
        raw = run_knowledge_base_rag(
            q,
            profile,
            allowed_doc_ids=kb_doc_ids if kb_doc_ids else None,
        )
    else:
        if doc_path is None:
            raw = {
                "answer": "",
                "error": "单文档 RAG 子 Agent 缺少 doc_path",
                "retrieved_chunks": [],
                "citations": [],
            }
        else:
            raw = run_document_rag(Path(doc_path), q, profile)

    audit_record(
        "rag_query_result",
        payload={
            "pipeline": pipeline,
            "question": q,
            "via_subagent": True,
            **rag_result_to_payload(raw),
        },
    )
    return _compact_subagent_result(raw, pipeline=pipeline)
