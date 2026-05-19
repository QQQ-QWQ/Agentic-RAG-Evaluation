"""全库 + 会话临时索引融合检索。"""

from __future__ import annotations

from unittest.mock import patch

from agentic_rag.documents.multi_doc import (
    RETRIEVAL_EPHEMERAL_ONLY,
    RETRIEVAL_FULL_KB,
    RETRIEVAL_FULL_KB_AND_EPHEMERAL,
    SessionDocumentScope,
    normalize_retrieval_mode,
)
from agentic_rag.experiment.session_rag import (
    run_combined_kb_ephemeral_rag,
    set_ephemeral_session_index,
)
from agentic_rag.pipelines.local_rag import merge_evidence_hits
from agentic_rag.rag.simple import SimpleVectorIndex
from agentic_rag.schemas import EvidenceChunk


def test_normalize_retrieval_mode_defaults() -> None:
    assert normalize_retrieval_mode(None, has_attachments=False) == RETRIEVAL_FULL_KB
    assert (
        normalize_retrieval_mode(None, has_attachments=True)
        == RETRIEVAL_FULL_KB_AND_EPHEMERAL
    )
    assert (
        normalize_retrieval_mode("combined", has_attachments=True)
        == RETRIEVAL_FULL_KB_AND_EPHEMERAL
    )


def test_session_scope_combine_flag() -> None:
    scope = SessionDocumentScope(
        use_ephemeral=True,
        retrieval_mode=RETRIEVAL_FULL_KB_AND_EPHEMERAL,
    )
    assert scope.combine_ephemeral_with_full_kb is True
    scope2 = SessionDocumentScope(
        use_ephemeral=True,
        retrieval_mode=RETRIEVAL_EPHEMERAL_ONLY,
    )
    assert scope2.combine_ephemeral_with_full_kb is False


def test_merge_evidence_hits_picks_best_score() -> None:
    a = EvidenceChunk(
        chunk_id="a::1",
        doc_id="a",
        text="a",
        score=0.5,
        source="",
    )
    b = EvidenceChunk(
        chunk_id="b::1",
        doc_id="b",
        text="b",
        score=0.9,
        source="",
    )
    merged = merge_evidence_hits([[a], [b]], top_k=2)
    assert len(merged) == 2
    assert merged[0].chunk_id == "b::1"


def test_run_combined_requires_ephemeral() -> None:
    set_ephemeral_session_index(None)
    out = run_combined_kb_ephemeral_rag("q?")
    assert out.get("error")
    assert "临时索引" in out["error"]


def test_run_combined_merges_two_indexes() -> None:
    kb = SimpleVectorIndex(
        chunks=["kb chunk"],
        vectors=[[1.0, 0.0]],
    )
    kb.chunk_metadata = [{"chunk_id": "doc_kb::chunk_0000", "doc_id": "doc_kb"}]
    ep = SimpleVectorIndex(
        chunks=["ephemeral chunk"],
        vectors=[[0.0, 1.0]],
    )
    ep.chunk_metadata = [{"chunk_id": "sess_000::chunk_0000", "doc_id": "sess_000"}]

    set_ephemeral_session_index(ep)
    try:
        fake_hit_kb = EvidenceChunk(
            chunk_id="doc_kb::chunk_0000",
            doc_id="doc_kb",
            text="kb chunk",
            score=0.9,
            source="kb",
        )
        fake_hit_ep = EvidenceChunk(
            chunk_id="sess_000::chunk_0000",
            doc_id="sess_000",
            text="ephemeral chunk",
            score=0.85,
            source="ep",
        )
        with (
            patch(
                "agentic_rag.experiment.session_rag.load_or_build_knowledge_index",
                return_value=kb,
            ),
            patch(
                "agentic_rag.experiment.session_rag.retrieve_merged_from_indexes",
                return_value=([fake_hit_kb, fake_hit_ep], {}, {}),
            ),
            patch(
                "agentic_rag.experiment.session_rag.generate_answer_from_hits",
                return_value=("merged answer", {"total_tokens": 1}),
            ),
            patch(
                "agentic_rag.experiment.session_rag._expand_merged_hits",
                side_effect=lambda hits, **_: hits,
            ),
            patch("pathlib.Path.is_file", return_value=True),
        ):
            out = run_combined_kb_ephemeral_rag("test question?")
        assert out["answer"] == "merged answer"
        assert out["retrieval_scope"] == "full_kb_and_ephemeral"
        assert len(out["retrieved_chunks"]) == 2
    finally:
        set_ephemeral_session_index(None)
