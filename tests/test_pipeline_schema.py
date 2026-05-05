from agentic_rag.pipelines import local_rag
from agentic_rag.rag.simple import SimpleVectorIndex
from agentic_rag.schemas import RewriteResult


def _index() -> SimpleVectorIndex:
    index = SimpleVectorIndex(
        chunks=["Python list slicing uses start stop step.", "Loops repeat blocks."],
        vectors=[[1.0, 0.0], [0.0, 1.0]],
    )
    index.doc_id = "python_notes"
    index.source = "python_notes.md"
    return index


def test_run_c0_output_schema(monkeypatch):
    monkeypatch.setattr(local_rag, "embed_texts", lambda texts, **_: [[1.0, 0.0]])
    monkeypatch.setattr(
        local_rag,
        "generate_answer_from_hits",
        lambda question, hits, **_: ("answer with citation", {"total_tokens": 3}),
    )

    result = local_rag.run_c0_with_index(_index(), "How does slicing work?", question_id="Q001")

    assert result["config"] == "c0_naive"
    assert result["question_id"] == "Q001"
    assert result["retrieval_queries"] == ["How does slicing work?"]
    assert result["retrieved_chunks"][0]["doc_id"] == "python_notes"
    assert result["citations"][0]["chunk_id"].startswith("python_notes::chunk_")
    assert result["error"] == ""


def test_run_c1_output_schema(monkeypatch):
    monkeypatch.setattr(local_rag, "embed_texts", lambda texts, **_: [[1.0, 0.0]])
    monkeypatch.setattr(
        local_rag,
        "rewrite_query",
        lambda question, **_: RewriteResult(
            need_rewrite=True,
            rewrite_reason="colloquial",
            rewritten_query="Python list slicing syntax",
            rewrite_type="colloquial",
        ),
    )
    monkeypatch.setattr(
        local_rag,
        "generate_answer_from_hits",
        lambda question, hits, **_: ("answer with citation", {"total_tokens": 3}),
    )

    result = local_rag.run_c1_with_index(_index(), "slicing咋用", question_id="Q002")

    assert result["config"] == "c1_rewrite"
    assert result["need_rewrite"] is True
    assert result["rewritten_query"] == "Python list slicing syntax"
    assert result["retrieval_queries"] == ["slicing咋用", "Python list slicing syntax"]
    assert "retrieved_chunks" in result
    assert result["error"] == ""


def test_run_c1_can_write_jsonl_log(monkeypatch, tmp_path):
    monkeypatch.setattr(local_rag, "embed_texts", lambda texts, **_: [[1.0, 0.0]])
    monkeypatch.setattr(
        local_rag,
        "rewrite_query",
        lambda question, **_: RewriteResult(
            need_rewrite=False,
            rewrite_reason="clear query",
            rewritten_query=question,
        ),
    )
    monkeypatch.setattr(
        local_rag,
        "generate_answer_from_hits",
        lambda question, hits, **_: ("answer with citation", {"total_tokens": 3}),
    )

    result = local_rag.run_c1_with_index(
        _index(),
        "How does slicing work?",
        question_id="Q003",
        log_dir=tmp_path,
    )

    assert result["log_path"]
    assert (tmp_path / "c1_rewrite" / "run_logs.jsonl").is_file()
