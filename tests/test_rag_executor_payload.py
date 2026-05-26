import json

from agentic_rag.deep_planning.rag_executor import _compact_subagent_result


def test_compact_subagent_result_keeps_evidence_and_citation_fields() -> None:
    raw = {
        "answer": "ok",
        "retrieval_queries": ["what is Self-RAG"],
        "retrieved_chunks": [
            {
                "doc_id": "doc_self_rag",
                "chunk_id": "doc_self_rag::chunk_0001",
                "score": 0.91,
                "text": "Self-RAG retrieves and critiques evidence before answering.",
            },
            {
                "doc_id": "doc_self_rag",
                "chunk_id": "doc_self_rag::chunk_0002",
                "score": 0.21,
                "text": "Background paragraph.",
            },
        ],
        "retrieved_chunk_ids": ["doc_self_rag::chunk_0001", "doc_self_rag::chunk_0002"],
        "evidence_grader_kept_chunk_ids": ["doc_self_rag::chunk_0001"],
        "final_citation_chunk_ids": ["doc_self_rag::chunk_0001"],
        "citations": [{"doc_id": "doc_self_rag", "chunk_id": "doc_self_rag::chunk_0001"}],
    }

    payload = json.loads(_compact_subagent_result(raw, pipeline="c3_lite_v2"))

    assert payload["retrieval_queries"] == ["what is Self-RAG"]
    assert payload["retrieved_chunk_ids"] == [
        "doc_self_rag::chunk_0001",
        "doc_self_rag::chunk_0002",
    ]
    assert payload["evidence_grader_kept_chunk_ids"] == ["doc_self_rag::chunk_0001"]
    assert payload["final_citation_chunk_ids"] == ["doc_self_rag::chunk_0001"]
    assert [ch["chunk_id"] for ch in payload["kept_evidence_chunks"]] == [
        "doc_self_rag::chunk_0001"
    ]
    assert "Self-RAG retrieves" in payload["kept_evidence_chunks"][0]["text_preview"]
