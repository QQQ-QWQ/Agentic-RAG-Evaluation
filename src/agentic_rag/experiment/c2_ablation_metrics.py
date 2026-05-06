"""C2 检索消融实验：指标汇总与 gold chunk 辅助判定（与 docs/experiment_notes 评测口径对齐）。"""

from __future__ import annotations

import json
from typing import Any


def gold_chunk_status(reference_row: dict[str, str] | None, top_chunk_ids: list[str]) -> str:
    """
    返回 gold chunk 命中状态。

    - ``pending``：`evidence_chunk_id` 未标注或为 pending（无法算 strict Recall@K）。
    - ``true`` / ``false``：已标注时是否在 Top-K chunk 列表中出现。
    """
    if not reference_row:
        return "pending"
    raw = (reference_row.get("evidence_chunk_id") or "").strip()
    if not raw or raw.lower() == "pending":
        return "pending"
    gold_ids = [x.strip() for x in raw.split(",") if x.strip()]
    if not gold_ids:
        return "pending"
    tops = set(top_chunk_ids)
    for gid in gold_ids:
        if gid in tops:
            return "true"
    return "false"


def gold_chunk_rank(reference_row: dict[str, str] | None, top_chunk_ids: list[str]) -> str:
    """首个命中 gold chunk 在 Top-K 中的名次（1-based）；未命中或未标注则为空字符串。"""
    if gold_chunk_status(reference_row, top_chunk_ids) != "true":
        return ""
    raw = (reference_row.get("evidence_chunk_id") or "").strip()
    gold_ids = [x.strip() for x in raw.split(",") if x.strip()]
    for rank, cid in enumerate(top_chunk_ids, start=1):
        if cid in gold_ids:
            return str(rank)
    return ""


def row_extend_ablation(
    base_row: dict[str, Any],
    *,
    variant_name: str,
    hybrid: bool,
    use_rerank: bool,
    context_neighbor_chunks: int,
    result: dict[str, Any],
    reference_row: dict[str, str] | None,
) -> dict[str, Any]:
    """在批量 CSV 行上追加消融维度与检索统计。"""
    top_ids: list[str] = []
    try:
        top_ids = json.loads(base_row.get("top_chunk_ids") or "[]")
    except (json.JSONDecodeError, TypeError):
        pass
    rq = result.get("retrieval_queries") or []
    rerank_u = (result.get("token_usage") or {}).get("rerank") or {}
    out = dict(base_row)
    out.update(
        {
            "experiment_variant": variant_name,
            "hybrid": hybrid,
            "use_rerank": use_rerank,
            "context_neighbor_chunks": context_neighbor_chunks,
            "retrieval_query_count": len(rq),
            "gold_chunk_hit": gold_chunk_status(reference_row, top_ids),
            "gold_chunk_rank": gold_chunk_rank(reference_row, top_ids),
            "rerank_total_tokens": rerank_u.get("total_tokens", ""),
        }
    )
    return out


def summarize_variant(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """从扩展后的结果行聚合与 experiment_notes 一致的摘要指标。"""
    n = len(rows)
    if n == 0:
        return {"n_questions": 0}

    errors = sum(1 for r in rows if str(r.get("error", "")).strip())

    def _truthy_doc_hit(r: dict[str, Any]) -> bool:
        v = r.get("top_contains_expected_doc")
        if isinstance(v, bool):
            return v
        s = str(v).strip().lower()
        return s in ("true", "1", "yes")

    doc_hits = sum(1 for r in rows if _truthy_doc_hit(r))

    latencies: list[float] = []
    tokens: list[float] = []
    rq_counts: list[float] = []
    for r in rows:
        try:
            if r.get("latency_ms") not in ("", None):
                latencies.append(float(r["latency_ms"]))
        except (TypeError, ValueError):
            pass
        try:
            if r.get("total_tokens") not in ("", None):
                tokens.append(float(r["total_tokens"]))
        except (TypeError, ValueError):
            pass
        try:
            if r.get("retrieval_query_count") not in ("", None):
                rq_counts.append(float(r["retrieval_query_count"]))
        except (TypeError, ValueError):
            pass

    gc_pending = sum(1 for r in rows if r.get("gold_chunk_hit") == "pending")
    gc_true = sum(1 for r in rows if r.get("gold_chunk_hit") == "true")
    gc_false = sum(1 for r in rows if r.get("gold_chunk_hit") == "false")
    gc_evaluable = gc_true + gc_false

    return {
        "n_questions": n,
        "error_count": errors,
        "expected_doc_hit_count": doc_hits,
        "expected_doc_hit_rate": doc_hits / n if n else 0.0,
        "mean_latency_ms": sum(latencies) / len(latencies) if latencies else None,
        "mean_total_tokens": sum(tokens) / len(tokens) if tokens else None,
        "mean_retrieval_query_count": sum(rq_counts) / len(rq_counts) if rq_counts else None,
        "gold_chunk_pending_count": gc_pending,
        "gold_chunk_hit_count": gc_true,
        "gold_chunk_miss_count": gc_false,
        "gold_chunk_recall_rate": (gc_true / gc_evaluable) if gc_evaluable else None,
        "note": "gold_chunk_* 仅在 evidence_chunk_id 非 pending 时有意义；否则看 expected_doc_*。",
    }
