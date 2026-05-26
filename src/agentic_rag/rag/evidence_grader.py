"""Lightweight evidence grading before answer generation."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

from agentic_rag import config
from agentic_rag.llm.deepseek import create_deepseek_client
from agentic_rag.llm.usage_strict import require_deepseek_chat_usage
from agentic_rag.schemas import EvidenceChunk

SupportType = Literal["direct", "partial", "background", "irrelevant"]


@dataclass(frozen=True, slots=True)
class EvidenceGrade:
    chunk_id: str
    relevance: float
    support_type: SupportType
    supported_claims: list[str]
    keep: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _usage_to_dict(usage: Any) -> dict[str, int]:
    if usage is None:
        return {}
    out: dict[str, int] = {}
    for attr in ("prompt_tokens", "completion_tokens", "total_tokens"):
        val = getattr(usage, attr, None)
        if val is not None:
            out[attr] = int(val)
    return out


def _extract_json_array(text: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads((text or "").strip())
        if isinstance(parsed, list):
            return [x for x in parsed if isinstance(x, dict)]
        if isinstance(parsed, dict) and isinstance(parsed.get("grades"), list):
            return [x for x in parsed["grades"] if isinstance(x, dict)]
    except json.JSONDecodeError:
        pass
    match = re.search(r"\[[\s\S]*\]", text or "")
    if not match:
        return []
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    return [x for x in parsed if isinstance(x, dict)] if isinstance(parsed, list) else []


def _coerce_support_type(value: Any) -> SupportType:
    s = str(value or "").strip().lower()
    if s in {"direct", "partial", "background", "irrelevant"}:
        return s  # type: ignore[return-value]
    return "background"


def _grade_heuristic(question: str, hits: list[EvidenceChunk]) -> list[EvidenceGrade]:
    terms = {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9_\-\u4e00-\u9fff]{2,}", question or "")
    }
    grades: list[EvidenceGrade] = []
    for i, hit in enumerate(hits):
        text = (hit.text or "").lower()
        overlap = sum(1 for term in terms if term in text)
        relevance = min(1.0, (overlap / max(1, len(terms))) + max(0.0, hit.score) * 0.2)
        support: SupportType
        if i < 2 or relevance >= 0.55:
            support = "direct"
        elif relevance >= 0.25:
            support = "partial"
        else:
            support = "irrelevant"
        grades.append(
            EvidenceGrade(
                chunk_id=hit.chunk_id,
                relevance=round(relevance, 4),
                support_type=support,
                supported_claims=[],
                keep=support in {"direct", "partial"},
            )
        )
    return grades


def grade_evidence_chunks(
    question: str,
    hits: list[EvidenceChunk],
    *,
    task_type: str = "",
    backend: str = "llm",
    max_chunks: int = 8,
    max_chunk_chars: int = 520,
) -> tuple[list[EvidenceGrade], dict[str, int]]:
    """Grade retrieved chunks and return structured keep/drop decisions."""
    if not hits:
        return [], {}
    candidates = hits[: max(1, max_chunks)]
    backend_n = (backend or "llm").strip().lower()
    if backend_n in {"heuristic", "rule", "rules", "none"}:
        return _grade_heuristic(question, candidates), {}
    if backend_n != "llm":
        raise ValueError(f"unknown evidence grader backend: {backend}")

    lines: list[str] = []
    for hit in candidates:
        snippet = (hit.text or "")[:max_chunk_chars].replace("\n", " ")
        lines.append(
            f"- chunk_id={hit.chunk_id} score={hit.score:.4f} text={snippet}"
        )

    prompt = (
        "Question:\n"
        f"{question}\n\n"
        "Task type:\n"
        f"{task_type or 'unknown'}\n\n"
        "Retrieved chunks:\n"
        + "\n".join(lines)
        + "\n\n"
        "Grade each chunk for whether it directly supports answering the question. "
        "Output ONLY a JSON array. Each item must contain: "
        "chunk_id, relevance (0..1), support_type, supported_claims, keep. "
        "support_type must be one of: direct, partial, background, irrelevant. "
        "Set keep=true only for direct or strong partial support. "
        "Use background sparingly."
    )

    client = create_deepseek_client()
    resp = client.chat.completions.create(
        model=config.DEEPSEEK_CHAT_MODEL or "deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": "You are an evidence filter. Output valid JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
    )
    usage = _usage_to_dict(getattr(resp, "usage", None))
    require_deepseek_chat_usage(usage, where="evidence_grader")
    raw = resp.choices[0].message.content or ""
    parsed = _extract_json_array(raw)
    by_id = {str(item.get("chunk_id") or ""): item for item in parsed}
    fallback = _grade_heuristic(question, candidates)
    grades: list[EvidenceGrade] = []
    for fb in fallback:
        item = by_id.get(fb.chunk_id, {})
        support = _coerce_support_type(item.get("support_type", fb.support_type))
        try:
            relevance = float(item.get("relevance", fb.relevance))
        except (TypeError, ValueError):
            relevance = fb.relevance
        claims = item.get("supported_claims")
        if not isinstance(claims, list):
            claims = []
        keep = bool(item.get("keep", fb.keep))
        grades.append(
            EvidenceGrade(
                chunk_id=fb.chunk_id,
                relevance=max(0.0, min(1.0, relevance)),
                support_type=support,
                supported_claims=[str(x) for x in claims[:3]],
                keep=keep,
            )
        )
    return grades, usage


def filter_hits_by_grades(
    hits: list[EvidenceChunk],
    grades: list[EvidenceGrade],
    *,
    task_type: str = "",
    min_partial_relevance: float = 0.55,
    max_background: int = 1,
    min_keep: int = 2,
) -> list[EvidenceChunk]:
    """Apply conservative grader decisions while preserving fallback evidence."""
    if not hits or not grades:
        return hits
    grade_by_id = {g.chunk_id: g for g in grades}
    kept: list[EvidenceChunk] = []
    background_count = 0
    for hit in hits:
        grade = grade_by_id.get(hit.chunk_id)
        if grade is None:
            continue
        if grade.support_type == "direct" and grade.keep:
            kept.append(hit)
        elif (
            grade.support_type == "partial"
            and grade.keep
            and grade.relevance >= min_partial_relevance
        ):
            kept.append(hit)
        elif (
            (task_type or "").strip() == "multi_doc"
            and grade.support_type == "background"
            and grade.keep
            and background_count < max_background
        ):
            kept.append(hit)
            background_count += 1
    if len(kept) >= min_keep:
        return kept
    # Keep enough top-ranked chunks to avoid over-filtering small or noisy result sets.
    out = kept[:]
    seen = {h.chunk_id for h in out}
    for hit in hits:
        if len(out) >= min_keep:
            break
        if hit.chunk_id not in seen:
            out.append(hit)
            seen.add(hit.chunk_id)
    return out
