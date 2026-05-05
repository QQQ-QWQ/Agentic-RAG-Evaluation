from agentic_rag.rewrite import (
    build_retrieval_queries,
    extract_json_object,
    normalize_rewrite_payload,
)


def test_extract_json_object_from_markdown_block():
    raw = """```json
{"need_rewrite": true, "rewrite_reason": "too vague", "rewritten_query": "list slicing in Python"}
```"""
    payload = extract_json_object(raw)
    assert payload["need_rewrite"] is True
    assert payload["rewritten_query"] == "list slicing in Python"


def test_normalize_rewrite_payload_keeps_original_when_empty():
    result = normalize_rewrite_payload(
        {"need_rewrite": True, "rewrite_reason": "empty", "rewritten_query": ""},
        original_query="What is list slicing?",
    )
    assert result.need_rewrite is False
    assert result.rewritten_query == "What is list slicing?"


def test_build_retrieval_queries_original_plus_rewritten():
    result = normalize_rewrite_payload(
        {
            "need_rewrite": True,
            "rewrite_reason": "colloquial",
            "rewritten_query": "Python list slicing syntax and examples",
        },
        original_query="How does slicing work?",
    )
    assert build_retrieval_queries("How does slicing work?", result) == [
        "How does slicing work?",
        "Python list slicing syntax and examples",
    ]
