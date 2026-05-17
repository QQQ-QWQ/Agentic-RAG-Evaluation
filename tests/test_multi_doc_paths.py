"""多文档路径解析测试。"""

from __future__ import annotations

from agentic_rag.documents.multi_doc import parse_document_paths_from_text


def test_parse_comma_separated():
    text = "data/raw/a.md, data/raw/b.md"
    paths = parse_document_paths_from_text(text)
    assert "data/raw/a.md" in paths
    assert "data/raw/b.md" in paths


def test_parse_natural_language():
    text = "请分析 data/raw/tech_docs/dify_readme.md 和 langchain_intro.md"
    paths = parse_document_paths_from_text(text)
    assert any("dify_readme.md" in p for p in paths)


def test_parse_multiline():
    text = "data/raw/a.md\ndata/raw/b.md"
    paths = parse_document_paths_from_text(text)
    assert len(paths) >= 2
