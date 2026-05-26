"""审计 payload 序列化与截断（仅落盘，不注入模型）。"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

DEFAULT_MAX_STR = 12_000
PREVIEW_MAX_STR = 2_000


def truncate_text(text: str, *, max_len: int = DEFAULT_MAX_STR) -> str:
    s = (text or "").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 12] + "\n…(truncated)"


def safe_json_obj(obj: Any, *, max_len: int = DEFAULT_MAX_STR) -> Any:
    """尽量 JSON 可序列化；过长字符串截断。"""
    if obj is None or isinstance(obj, (bool, int, float)):
        return obj
    if isinstance(obj, str):
        return truncate_text(obj, max_len=max_len)
    if isinstance(obj, dict):
        return {str(k): safe_json_obj(v, max_len=max_len // 2) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [safe_json_obj(x, max_len=max_len // 4) for x in obj[:80]]
    if is_dataclass(obj):
        return safe_json_obj(asdict(obj), max_len=max_len)
    return truncate_text(str(obj), max_len=PREVIEW_MAX_STR)


def plan_to_payload(plan: Any) -> dict[str, Any]:
    if plan is None:
        return {}
    raw = getattr(plan, "raw", None) or {}
    out: dict[str, Any] = {
        "document_path": getattr(plan, "document_path", None),
        "task_summary": getattr(plan, "task_summary", ""),
        "needs_retrieval_tools": getattr(plan, "needs_retrieval_tools", None),
        "suggested_pipelines": list(getattr(plan, "suggested_pipelines", []) or []),
        "plan_for_layer2": getattr(plan, "plan_for_layer2", ""),
        "reasoning_brief": getattr(plan, "reasoning_brief", ""),
        "kb_mutation_intent": getattr(plan, "kb_mutation_intent", None),
        "needs_web_tools": getattr(plan, "needs_web_tools", None),
        "web_urls": list(getattr(plan, "web_urls", []) or []),
        "local_paths": list(getattr(plan, "local_paths", []) or []),
        "raw": safe_json_obj(raw),
    }
    return safe_json_obj(out, max_len=DEFAULT_MAX_STR)


def verdict_to_payload(verdict: Any) -> dict[str, Any]:
    if verdict is None:
        return {}
    out: dict[str, Any] = {
        "verdict": getattr(verdict, "verdict", ""),
        "summary_for_user": getattr(verdict, "summary_for_user", ""),
        "hint_for_next_planner": getattr(verdict, "hint_for_next_planner", None),
        "hint_for_next_execution": getattr(verdict, "hint_for_next_execution", None),
        "reasoning_brief": getattr(verdict, "reasoning_brief", ""),
        "support_verdict": getattr(verdict, "support_verdict", "unknown"),
        "unsupported_claims": list(getattr(verdict, "unsupported_claims", []) or []),
        "missing_required_items": list(
            getattr(verdict, "missing_required_items", []) or []
        ),
        "citation_mismatches": list(getattr(verdict, "citation_mismatches", []) or []),
        "revision_instruction": getattr(verdict, "revision_instruction", None),
        "raw": safe_json_obj(getattr(verdict, "raw", {}) or {}),
    }
    return safe_json_obj(out, max_len=DEFAULT_MAX_STR)


def _tool_call_entry(tc: Any) -> dict[str, Any]:
    if isinstance(tc, dict):
        return {
            "id": tc.get("id"),
            "name": tc.get("name"),
            "args": safe_json_obj(tc.get("args") or {}),
        }
    return safe_json_obj(tc, max_len=PREVIEW_MAX_STR)


def message_to_audit_dict(message: Any) -> dict[str, Any]:
    """LangChain Message → 可审计 dict。"""
    cls = type(message).__name__
    out: dict[str, Any] = {"message_type": cls}
    content = getattr(message, "content", None)
    if isinstance(content, str):
        out["content"] = truncate_text(content, max_len=PREVIEW_MAX_STR)
    elif content is not None:
        out["content"] = safe_json_obj(content, max_len=PREVIEW_MAX_STR)
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        out["tool_calls"] = [_tool_call_entry(tc) for tc in tool_calls[:20]]
    name = getattr(message, "name", None)
    if name:
        out["name"] = name
    tid = getattr(message, "tool_call_id", None)
    if tid:
        out["tool_call_id"] = tid
    return out


def serialize_agent_messages(messages: list[Any], *, tail: int = 40) -> list[dict[str, Any]]:
    if not messages:
        return []
    slice_msgs = messages[-tail:] if tail > 0 else messages
    return [message_to_audit_dict(m) for m in slice_msgs]


def rag_result_to_payload(raw: dict[str, Any], *, max_chunks: int = 24) -> dict[str, Any]:
    chunks = raw.get("retrieved_chunks") or []
    slim_chunks: list[dict[str, Any]] = []
    for ch in chunks[:max_chunks]:
        if not isinstance(ch, dict):
            continue
        slim_chunks.append(
            {
                "chunk_id": ch.get("chunk_id"),
                "doc_id": ch.get("doc_id"),
                "score": ch.get("score"),
                "source": ch.get("source"),
                "text_preview": truncate_text(str(ch.get("text") or ""), max_len=600),
            }
        )
    return safe_json_obj(
        {
            "config": raw.get("config"),
            "retrieval_scope": raw.get("retrieval_scope"),
            "original_query": raw.get("original_query"),
            "retrieval_queries": raw.get("retrieval_queries"),
            "sub_queries": raw.get("sub_queries") or raw.get("retrieval_queries"),
            "rewritten_query": raw.get("rewritten_query"),
            "answer": raw.get("answer"),
            "error": raw.get("error"),
            "latency_ms": raw.get("latency_ms"),
            "citations": raw.get("citations"),
            "retrieved_chunk_ids": raw.get("retrieved_chunk_ids") or [],
            "expanded_chunk_ids": raw.get("expanded_chunk_ids") or [],
            "final_citation_chunk_ids": raw.get("final_citation_chunk_ids") or [],
            "multi_query_fusion": raw.get("multi_query_fusion"),
            "rrf_input_count": raw.get("rrf_input_count"),
            "rrf_output_chunk_ids": raw.get("rrf_output_chunk_ids") or [],
            "evidence_grader_kept_chunk_ids": raw.get("evidence_grader_kept_chunk_ids") or [],
            "kept_evidence_chunks": raw.get("kept_evidence_chunks") or [],
            "chunk_count": len(chunks) if isinstance(chunks, list) else 0,
            "retrieved_chunks": slim_chunks,
        },
        max_len=DEFAULT_MAX_STR,
    )
