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
            "rewrite_confidence": 0.8,
            "rewrite_reason": "colloquial",
            "rewritten_query": "Python list slicing syntax and examples",
        },
        original_query="How does slicing work?",
    )
    assert build_retrieval_queries("How does slicing work?", result) == [
        "How does slicing work?",
        "Python list slicing syntax and examples",
    ]


def test_build_retrieval_queries_uses_multiple_candidates():
    result = normalize_rewrite_payload(
        {
            "need_rewrite": True,
            "rewrite_confidence": 0.9,
            "rewrite_reason": "query is colloquial",
            "rewrite_type": "colloquial",
            "rewritten_query": "Python list slicing middle elements start stop",
            "rewritten_queries": [
                "Python list slicing middle elements start stop",
                "list[start:stop] Python slicing example",
                "Python nums[1:4] slicing output",
            ],
        },
        original_query="How does slicing work?",
    )

    assert result.need_rewrite is True
    assert result.rewrite_confidence == 0.9
    assert result.rewritten_queries == [
        "Python list slicing middle elements start stop",
        "list[start:stop] Python slicing example",
        "Python nums[1:4] slicing output",
    ]
    assert build_retrieval_queries("How does slicing work?", result) == [
        "How does slicing work?",
        "Python list slicing middle elements start stop",
        "list[start:stop] Python slicing example",
        "Python nums[1:4] slicing output",
    ]


def test_low_confidence_rewrite_is_suppressed():
    result = normalize_rewrite_payload(
        {
            "need_rewrite": True,
            "rewrite_confidence": 0.3,
            "rewrite_reason": "uncertain rewrite",
            "rewrite_type": "fuzzy_query",
            "rewritten_query": "possibly unrelated query",
            "rewritten_queries": ["possibly unrelated query"],
        },
        original_query="What is RAGAS?",
    )

    assert result.need_rewrite is False
    assert result.rewritten_query == "What is RAGAS?"
    assert result.rewritten_queries == []
    assert build_retrieval_queries("What is RAGAS?", result) == ["What is RAGAS?"]


def test_build_retrieval_queries_from_dict_candidates():
    queries = build_retrieval_queries(
        "切片咋取中间几个元素？",
        {
            "need_rewrite": True,
            "rewritten_query": "Python 列表切片 获取中间元素",
            "rewritten_queries": [
                "Python 列表切片 获取中间元素",
                "list[start:stop] Python slicing",
            ],
        },
    )

    assert queries == [
        "切片咋取中间几个元素？",
        "Python 列表切片 获取中间元素",
        "list[start:stop] Python slicing",
    ]
