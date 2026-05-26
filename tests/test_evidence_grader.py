from agentic_rag.rag.evidence_grader import (
    EvidenceGrade,
    filter_hits_by_grades,
    grade_evidence_chunks,
)
from agentic_rag.schemas import EvidenceChunk


def _hit(chunk_id: str, text: str, score: float = 0.5) -> EvidenceChunk:
    return EvidenceChunk(
        chunk_id=chunk_id,
        doc_id="doc_x",
        text=text,
        score=score,
        rank=int(chunk_id.rsplit("_", 1)[-1]) + 1,
    )


def test_heuristic_evidence_grader_returns_required_fields():
    hits = [
        _hit("doc_x::chunk_0000", "Python list slice start stop step", 0.8),
        _hit("doc_x::chunk_0001", "unrelated material", 0.1),
    ]

    grades, usage = grade_evidence_chunks(
        "Python list slice",
        hits,
        backend="heuristic",
    )

    assert usage == {}
    assert len(grades) == 2
    assert grades[0].chunk_id == "doc_x::chunk_0000"
    assert grades[0].support_type in {"direct", "partial", "background", "irrelevant"}
    assert isinstance(grades[0].to_dict()["keep"], bool)


def test_filter_hits_keeps_direct_and_limits_background():
    hits = [
        _hit("doc_x::chunk_0000", "direct"),
        _hit("doc_x::chunk_0001", "background"),
        _hit("doc_x::chunk_0002", "background 2"),
    ]
    grades = [
        EvidenceGrade("doc_x::chunk_0000", 0.9, "direct", [], True),
        EvidenceGrade("doc_x::chunk_0001", 0.7, "background", [], True),
        EvidenceGrade("doc_x::chunk_0002", 0.7, "background", [], True),
    ]

    kept = filter_hits_by_grades(
        hits,
        grades,
        task_type="multi_doc",
        min_keep=1,
    )

    assert [hit.chunk_id for hit in kept] == [
        "doc_x::chunk_0000",
        "doc_x::chunk_0001",
    ]


def test_filter_hits_falls_back_to_minimum_evidence():
    hits = [
        _hit("doc_x::chunk_0000", "top"),
        _hit("doc_x::chunk_0001", "second"),
    ]
    grades = [
        EvidenceGrade("doc_x::chunk_0000", 0.1, "irrelevant", [], False),
        EvidenceGrade("doc_x::chunk_0001", 0.1, "irrelevant", [], False),
    ]

    kept = filter_hits_by_grades(hits, grades, min_keep=2)

    assert [hit.chunk_id for hit in kept] == [
        "doc_x::chunk_0000",
        "doc_x::chunk_0001",
    ]
