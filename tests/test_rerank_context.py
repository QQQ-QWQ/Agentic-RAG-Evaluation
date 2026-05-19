"""重排与上下文扩展接线（mock 向量与生成，不调外部 API）。"""

from agentic_rag.pipelines import local_rag
from agentic_rag.rag.context_expand import expand_hits_with_neighbors
from agentic_rag.rag.simple import SimpleVectorIndex
from agentic_rag.schemas import EvidenceChunk


def _four_chunk_index() -> SimpleVectorIndex:
    index = SimpleVectorIndex(
        chunks=[
            "chunk0 alpha",
            "chunk1 gamma beta",
            "chunk2 gamma",
            "chunk3 gamma delta",
        ],
        vectors=[
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
    )
    index.doc_id = "doc_x"
    index.source = "doc_x.md"
    return index


def test_retrieve_rerank_none_truncates_pool(monkeypatch):
    monkeypatch.setattr(
        local_rag,
        "embed_texts",
        lambda texts, **_: [[0.0, 0.0, 1.0, 0.0]],
    )

    hits, usage, ark_usage = local_rag.retrieve_with_index(
        _four_chunk_index(),
        ["gamma"],
        top_k=2,
        rerank=True,
        rerank_backend="none",
        rerank_pool_size=4,
    )
    assert usage == {}
    assert isinstance(ark_usage, dict)
    assert len(hits) == 2
    assert hits[0].chunk_id.endswith("chunk_0002")


def test_run_c0_context_neighbors_expand(monkeypatch):
    monkeypatch.setattr(
        local_rag,
        "embed_texts",
        lambda texts, **_: [[0.0, 0.0, 1.0, 0.0]],
    )
    monkeypatch.setattr(
        local_rag,
        "generate_answer_from_hits",
        lambda question, hits, **_: ("ok", {"total_tokens": 1}),
    )

    result = local_rag.run_c0_with_index(
        _four_chunk_index(),
        "about gamma",
        task_type="fuzzy_query",
        context_neighbor_chunks=1,
    )
    assert result["error"] == ""
    body = result["retrieved_chunks"][0]["text"]
    assert "chunk1 gamma beta" in body
    assert "chunk2 gamma" in body
    assert "chunk3 gamma delta" in body
    assert result["context_expansion"][0]["applied"] is True
    assert result["context_expansion"][0]["expanded_chunk_ids"] == [
        "doc_x::chunk_0001",
        "doc_x::chunk_0002",
        "doc_x::chunk_0003",
    ]
    assert result["retrieved_chunk_ids"][0] == "doc_x::chunk_0002"
    assert result["expanded_chunk_ids"] == [
        "doc_x::chunk_0001",
        "doc_x::chunk_0003",
    ]
    assert result["final_citation_chunk_ids"][0] == "doc_x::chunk_0002"


def test_context_neighbors_skip_simple_qa(monkeypatch):
    monkeypatch.setattr(
        local_rag,
        "embed_texts",
        lambda texts, **_: [[0.0, 0.0, 1.0, 0.0]],
    )
    monkeypatch.setattr(
        local_rag,
        "generate_answer_from_hits",
        lambda question, hits, **_: ("ok", {"total_tokens": 1}),
    )

    result = local_rag.run_c0_with_index(
        _four_chunk_index(),
        "about gamma",
        task_type="simple_qa",
        context_neighbor_chunks=1,
    )
    assert result["error"] == ""
    body = result["retrieved_chunks"][0]["text"]
    assert body == "chunk2 gamma"
    assert result["context_expansion"][0]["applied"] is False
    assert result["context_expansion"][0]["reason"] == "task_type_not_eligible:simple_qa"


def test_selective_context_expansion_stops_at_heading_boundary():
    index = SimpleVectorIndex(
        chunks=[
            "section A target context",
            "target evidence",
            "## Section B\nunrelated context",
            "more unrelated context",
        ],
        vectors=[[1.0], [1.0], [1.0], [1.0]],
    )
    index.doc_id = "doc_h"
    hit = EvidenceChunk(
        chunk_id="doc_h::chunk_0001",
        doc_id="doc_h",
        text="target evidence",
        score=1.0,
        rank=1,
    )

    expanded = expand_hits_with_neighbors(
        [hit],
        index,
        neighbors=2,
        selective=True,
        task_type="multi_doc",
        question="target evidence",
    )

    assert expanded[0].context_expansion_applied is True
    assert expanded[0].expanded_chunk_ids == ["doc_h::chunk_0000", "doc_h::chunk_0001"]
    assert "section A target context" in expanded[0].text
    assert "Section B" not in expanded[0].text


def test_selective_context_expansion_does_not_require_query_keyword():
    index = SimpleVectorIndex(
        chunks=[
            "unrelated previous",
            "target evidence",
            "target follow up detail",
        ],
        vectors=[[1.0], [1.0], [1.0]],
    )
    index.doc_id = "doc_k"
    hit = EvidenceChunk(
        chunk_id="doc_k::chunk_0001",
        doc_id="doc_k",
        text="target evidence",
        score=1.0,
        rank=1,
    )

    expanded = expand_hits_with_neighbors(
        [hit],
        index,
        neighbors=1,
        selective=True,
        task_type="multi_doc",
        question="target",
    )

    assert expanded[0].context_expansion_applied is True
    assert expanded[0].expanded_chunk_ids == [
        "doc_k::chunk_0000",
        "doc_k::chunk_0001",
        "doc_k::chunk_0002",
    ]
    assert "unrelated previous" in expanded[0].text
    assert "target follow up detail" in expanded[0].text


def test_selective_context_expansion_skips_when_budget_exceeded():
    index = SimpleVectorIndex(
        chunks=[
            "target previous " * 20,
            "target evidence",
            "target next " * 20,
        ],
        vectors=[[1.0], [1.0], [1.0]],
    )
    index.doc_id = "doc_b"
    hit = EvidenceChunk(
        chunk_id="doc_b::chunk_0001",
        doc_id="doc_b",
        text="target evidence",
        score=1.0,
        rank=1,
    )

    expanded = expand_hits_with_neighbors(
        [hit],
        index,
        neighbors=1,
        selective=True,
        task_type="multi_doc",
        question="target",
        max_context_chars=20,
    )

    assert expanded[0].context_expansion_applied is False
    assert expanded[0].context_expansion_reason == "context_budget_exceeded"
    assert expanded[0].text == "target evidence"


def test_run_c0_token_usage_includes_rerank_slot(monkeypatch):
    monkeypatch.setattr(
        local_rag,
        "embed_texts",
        lambda texts, **_: [[1.0, 0.0, 0.0, 0.0]],
    )
    monkeypatch.setattr(
        local_rag,
        "generate_answer_from_hits",
        lambda question, hits, **_: ("ok", {"total_tokens": 1}),
    )

    result = local_rag.run_c0_with_index(
        _four_chunk_index(),
        "q",
        use_rerank=False,
    )
    assert "rerank" in result["token_usage"]
    assert result["token_usage"]["rerank"] == {}
