"""Post-retrieval context expansion helpers."""

from __future__ import annotations

import re
from collections.abc import Iterable

from agentic_rag.rag.simple import SimpleVectorIndex
from agentic_rag.schemas import EvidenceChunk


_CHUNK_TAIL_RE = re.compile(r"::chunk_(\d+)$")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S")

DEFAULT_EXPAND_TASK_TYPES = frozenset({"fuzzy_query", "multi_doc", "insufficient_evidence"})
SKIP_EXPAND_TASK_TYPES = frozenset({"simple_qa", "calculation", "code_execution", "table_analysis"})


def chunk_index_from_id(chunk_id: str) -> int | None:
    m = _CHUNK_TAIL_RE.search(chunk_id.strip())
    if not m:
        return None
    return int(m.group(1))


def _chunk_metadata(index: SimpleVectorIndex, pos: int) -> dict:
    metadata = getattr(index, "chunk_metadata", None)
    if isinstance(metadata, list) and 0 <= pos < len(metadata):
        item = metadata[pos]
        if isinstance(item, dict):
            return item
    return {}


def _chunk_id_at(index: SimpleVectorIndex, pos: int, fallback_doc_id: str) -> str:
    meta = _chunk_metadata(index, pos)
    return str(meta.get("chunk_id") or f"{fallback_doc_id}::chunk_{pos:04d}")


def _doc_id_at(index: SimpleVectorIndex, pos: int, fallback_doc_id: str) -> str:
    meta = _chunk_metadata(index, pos)
    return str(meta.get("doc_id") or fallback_doc_id or getattr(index, "doc_id", "doc_001"))


def _position_for_hit(index: SimpleVectorIndex, hit: EvidenceChunk) -> int | None:
    metadata = getattr(index, "chunk_metadata", None)
    if isinstance(metadata, list):
        for pos, meta in enumerate(metadata):
            if not isinstance(meta, dict):
                continue
            if str(meta.get("chunk_id") or "") == hit.chunk_id:
                return pos

    idx = chunk_index_from_id(hit.chunk_id)
    if idx is not None and 0 <= idx < len(index.chunks):
        return idx
    return None


def _starts_with_heading(text: str) -> bool:
    return bool(_HEADING_RE.match(text or ""))


def _eligible_by_task(task_type: str, question: str) -> tuple[bool, str]:
    task = (task_type or "").strip()
    if task in SKIP_EXPAND_TASK_TYPES:
        return False, f"task_type_not_eligible:{task}"
    if task in DEFAULT_EXPAND_TASK_TYPES:
        return True, f"task_type:{task}"
    return False, "no_context_trigger"


def _within_same_section(
    index: SimpleVectorIndex,
    *,
    current_pos: int,
    candidate_pos: int,
    doc_id: str,
) -> bool:
    if not (0 <= candidate_pos < len(index.chunks)):
        return False
    if _doc_id_at(index, candidate_pos, doc_id) != doc_id:
        return False

    candidate = index.chunks[candidate_pos]
    if candidate_pos > current_pos and _starts_with_heading(candidate):
        return False
    return True


def _copy_hit_with_expansion(
    hit: EvidenceChunk,
    *,
    text: str | None = None,
    expanded_chunk_ids: Iterable[str] | None = None,
    applied: bool,
    reason: str,
) -> EvidenceChunk:
    return EvidenceChunk(
        chunk_id=hit.chunk_id,
        doc_id=hit.doc_id,
        text=hit.text if text is None else text,
        score=hit.score,
        source=hit.source,
        page=hit.page,
        rank=hit.rank,
        query=hit.query,
        expanded_chunk_ids=list(expanded_chunk_ids or [hit.chunk_id]),
        context_expansion_applied=applied,
        context_expansion_reason=reason,
    )


def _expand_positions(
    index: SimpleVectorIndex,
    *,
    center_pos: int,
    doc_id: str,
    neighbors: int,
) -> list[int]:
    positions = [center_pos]

    for offset in range(1, neighbors + 1):
        pos = center_pos - offset
        if not _within_same_section(index, current_pos=center_pos, candidate_pos=pos, doc_id=doc_id):
            break
        positions.insert(0, pos)

    for offset in range(1, neighbors + 1):
        pos = center_pos + offset
        if not _within_same_section(index, current_pos=center_pos, candidate_pos=pos, doc_id=doc_id):
            break
        positions.append(pos)

    return positions


def expand_hits_with_neighbors(
    hits: list[EvidenceChunk],
    index: SimpleVectorIndex,
    *,
    neighbors: int,
    selective: bool = False,
    task_type: str = "",
    question: str = "",
    max_expanded_hits: int = 3,
    min_relative_score: float = 0.5,
    max_context_chars: int = 6000,
) -> list[EvidenceChunk]:
    """
    Expand retrieved chunks with neighboring chunks.

    The default keeps the previous behavior: every hit is expanded with +/- N
    neighboring chunks. With ``selective=True``, C2 Stage3 uses a conservative
    policy: expand only context-heavy task types, high-ranked/high-scored hits,
    stay inside the same document/section boundary, and obey a context budget.
    """
    if neighbors <= 0 or not hits:
        return hits
    if not index.chunks:
        return hits

    if selective:
        return expand_hits_selectively(
            hits,
            index,
            neighbors=neighbors,
            task_type=task_type,
            question=question,
            max_expanded_hits=max_expanded_hits,
            min_relative_score=min_relative_score,
            max_context_chars=max_context_chars,
        )

    out: list[EvidenceChunk] = []
    for hit in hits:
        pos = _position_for_hit(index, hit)
        if pos is None:
            out.append(
                _copy_hit_with_expansion(
                    hit,
                    applied=False,
                    reason="chunk_position_not_found",
                )
            )
            continue
        lo = max(0, pos - neighbors)
        hi = min(len(index.chunks), pos + neighbors + 1)
        positions = list(range(lo, hi))
        expanded_ids = [_chunk_id_at(index, p, hit.doc_id) for p in positions]
        merged = "\n\n---\n\n".join(index.chunks[p] for p in positions)
        out.append(
            _copy_hit_with_expansion(
                hit,
                text=merged,
                expanded_chunk_ids=expanded_ids,
                applied=len(expanded_ids) > 1,
                reason="fixed_neighbor_expansion",
            )
        )
    return out


def expand_hits_selectively(
    hits: list[EvidenceChunk],
    index: SimpleVectorIndex,
    *,
    neighbors: int,
    task_type: str = "",
    question: str = "",
    max_expanded_hits: int = 3,
    min_relative_score: float = 0.5,
    max_context_chars: int = 6000,
) -> list[EvidenceChunk]:
    """Selective context expansion for C2 Stage3-final."""
    eligible, trigger_reason = _eligible_by_task(task_type, question)
    if not eligible:
        return [
            _copy_hit_with_expansion(hit, applied=False, reason=trigger_reason)
            for hit in hits
        ]

    top_score = max((hit.score for hit in hits), default=0.0)
    score_threshold = top_score * min_relative_score if top_score > 0 else None
    expanded_count = 0
    used_chars = 0
    out: list[EvidenceChunk] = []

    for hit in hits:
        rank = hit.rank or (len(out) + 1)
        if expanded_count >= max_expanded_hits:
            out.append(_copy_hit_with_expansion(hit, applied=False, reason="max_expanded_hits_reached"))
            continue
        if rank > max_expanded_hits:
            out.append(_copy_hit_with_expansion(hit, applied=False, reason=f"rank_not_eligible:{rank}"))
            continue
        if score_threshold is not None and hit.score < score_threshold:
            out.append(_copy_hit_with_expansion(hit, applied=False, reason="score_below_relative_threshold"))
            continue

        center = _position_for_hit(index, hit)
        if center is None:
            out.append(_copy_hit_with_expansion(hit, applied=False, reason="chunk_position_not_found"))
            continue

        positions = _expand_positions(
            index,
            center_pos=center,
            doc_id=hit.doc_id,
            neighbors=neighbors,
        )
        if len(positions) <= 1:
            out.append(_copy_hit_with_expansion(hit, applied=False, reason="no_neighbor_within_section"))
            continue

        merged = "\n\n---\n\n".join(index.chunks[pos] for pos in positions)
        reason = f"selective_context_expansion:{trigger_reason}"
        if used_chars + len(merged) > max_context_chars:
            remaining = max_context_chars - used_chars
            if remaining <= len(hit.text):
                out.append(_copy_hit_with_expansion(hit, applied=False, reason="context_budget_exceeded"))
                continue
            merged = merged[:remaining]
            reason = f"{reason}:truncated_to_budget"

        used_chars += len(merged)
        expanded_count += 1
        out.append(
            _copy_hit_with_expansion(
                hit,
                text=merged,
                expanded_chunk_ids=[_chunk_id_at(index, pos, hit.doc_id) for pos in positions],
                applied=True,
                reason=reason,
            )
        )

    return out
