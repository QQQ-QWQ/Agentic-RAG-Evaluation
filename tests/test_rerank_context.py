"""重排与上下文扩展接线（mock 向量与生成，不调外部 API）。"""

from agentic_rag.pipelines import local_rag
from agentic_rag.rag.context_expand import expand_hits_with_neighbors
from agentic_rag.rag.simple import SimpleVectorIndex
from agentic_rag.schemas import EvidenceChunk


def _four_chunk_index() -> SimpleVectorIndex:
    index = SimpleVectorIndex(
        chunks=[
            "chunk0 alpha",
            "chunk1 beta",
            "chunk2 gamma",
            "chunk3 delta",
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
    assert "chunk1 beta" in body and "chunk2 gamma" in body and "chunk3 delta" in body
    assert result["context_expansion"][0]["applied"] is True
    assert result["context_expansion"][0]["expanded_chunk_ids"] == [
        "doc_x::chunk_0001",
        "doc_x::chunk_0002",
        "doc_x::chunk_0003",
    ]


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
            "section A context",
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
    )

    assert expanded[0].context_expansion_applied is True
    assert expanded[0].expanded_chunk_ids == ["doc_h::chunk_0000", "doc_h::chunk_0001"]
    assert "section A context" in expanded[0].text
    assert "Section B" not in expanded[0].text


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
