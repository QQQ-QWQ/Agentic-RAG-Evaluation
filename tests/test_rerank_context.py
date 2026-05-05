"""重排与上下文扩展接线（mock 向量与生成，不调外部 API）。"""

from agentic_rag.pipelines import local_rag
from agentic_rag.rag.simple import SimpleVectorIndex


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

    hits, usage = local_rag.retrieve_with_index(
        _four_chunk_index(),
        ["gamma"],
        top_k=2,
        rerank=True,
        rerank_backend="none",
        rerank_pool_size=4,
    )
    assert usage == {}
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
        context_neighbor_chunks=1,
    )
    assert result["error"] == ""
    body = result["retrieved_chunks"][0]["text"]
    assert "chunk1 beta" in body and "chunk2 gamma" in body and "chunk3 delta" in body


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
