"""session_planner JSON 抽取（无 API）。"""

import json

import pytest

from agentic_rag.deep_planning import session_planner


def test_extract_json_plain() -> None:
    text = '{"a": 1, "b": "x"}'
    d = session_planner._extract_json_object(text)
    assert d["a"] == 1


def test_extract_json_fence() -> None:
    text = 'Sure\n```json\n{"document_path": "E:\\\\a.pdf"}\n```'
    d = session_planner._extract_json_object(text)
    assert "document_path" in d


def test_extract_json_embedded() -> None:
    text = 'prefix {"task_summary": "hi"} suffix'
    d = session_planner._extract_json_object(text)
    assert d["task_summary"] == "hi"


def test_extract_invalid() -> None:
    with pytest.raises((ValueError, json.JSONDecodeError)):
        session_planner._extract_json_object("no json here")
