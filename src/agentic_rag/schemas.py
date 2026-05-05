from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class QueryTask:
    question: str
    question_id: str = ""
    task_type: str = ""
    doc_scope: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RewriteResult:
    need_rewrite: bool
    rewrite_reason: str
    rewritten_query: str
    rewrite_type: str = "none"
    raw_output: str = ""
    token_usage: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EvidenceChunk:
    chunk_id: str
    doc_id: str
    text: str
    score: float
    source: str = ""
    page: int | None = None
    rank: int | None = None
    query: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
