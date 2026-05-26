"""Firecrawl 工具封装单测（mock SDK，不调用外网）。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from agentic_rag.tools import firecrawl_tool as fc


def test_normalize_http_url():
    assert fc.normalize_http_url("https://example.com/a") == "https://example.com/a"
    assert fc.normalize_http_url("example.com/a") == "https://example.com/a"
    assert fc.normalize_http_url("") is None


def test_scrape_without_api_key(monkeypatch):
    monkeypatch.setattr(fc.config, "FIRECRAWL_API_KEY", None)
    res = fc.scrape_url("https://example.com")
    assert not res.ok
    assert "FIRECRAWL_API_KEY" in (res.error or "")


@patch("firecrawl.Firecrawl")
def test_scrape_success(mock_cls, monkeypatch, tmp_path: Path):
    monkeypatch.setattr(fc.config, "FIRECRAWL_API_KEY", "fc-test")
    monkeypatch.setattr(fc.config, "FIRECRAWL_MAX_OUTPUT_CHARS", 10_000)
    mock_client = MagicMock()
    mock_cls.return_value = mock_client
    mock_client.scrape.return_value = {
        "markdown": "# Hello\n\nbody",
        "metadata": {"title": "Hello", "sourceURL": "https://example.com"},
    }
    res = fc.scrape_url("https://example.com")
    assert res.ok
    assert "Hello" in res.markdown
    assert res.title == "Hello"


@patch("firecrawl.Firecrawl")
def test_search_success(mock_cls, monkeypatch):
    monkeypatch.setattr(fc.config, "FIRECRAWL_API_KEY", "fc-test")
    mock_client = MagicMock()
    mock_cls.return_value = mock_client
    mock_client.search.return_value = {
        "web": [
            {"url": "https://a.com", "title": "A", "description": "desc", "position": 1},
        ],
    }
    res = fc.search_web("test query", limit=3)
    assert res.ok
    assert len(res.items) == 1
    assert res.items[0]["url"] == "https://a.com"


def test_extract_urls_from_text():
    text = "请看 https://docs.firecrawl.dev/zh/introduction 和 www.example.com/page"
    urls = fc.extract_http_urls_from_text(text)
    assert any("firecrawl.dev" in u for u in urls)
    assert any("example.com" in u for u in urls)


def test_build_tools_c3_has_no_firecrawl_even_with_key(monkeypatch):
    monkeypatch.setattr(fc.config, "FIRECRAWL_API_KEY", "fc-test")
    from agentic_rag.deep_planning.tools_factory import build_topic4_rag_tools

    names_c3 = {getattr(t, "name", "") for t in build_topic4_rag_tools(enable_c4_tools=False)}
    assert "topic4_firecrawl_scrape" not in names_c3
    assert "topic4_file_read" not in names_c3
    assert "topic4_file_ingest" not in names_c3

    names_c4 = {getattr(t, "name", "") for t in build_topic4_rag_tools(enable_c4_tools=True)}
    assert "topic4_firecrawl_scrape" in names_c4
    assert "topic4_firecrawl_search" in names_c4
    assert "topic4_firecrawl_scrape_to_kb" in names_c4
    assert "topic4_file_read" in names_c4
    assert "topic4_file_ingest" in names_c4
    assert "topic4_kb_ingest" not in names_c4
    assert "topic4_file_to_markdown" not in names_c4


def test_build_tools_no_firecrawl_without_key(monkeypatch):
    monkeypatch.setattr(fc.config, "FIRECRAWL_API_KEY", None)
    from agentic_rag.deep_planning.tools_factory import build_topic4_rag_tools

    names = {getattr(t, "name", "") for t in build_topic4_rag_tools(enable_c4_tools=True)}
    assert "topic4_firecrawl_scrape" not in names
