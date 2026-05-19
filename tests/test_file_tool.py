"""C4 本地文件工具（topic4_file_read / topic4_file_ingest 底层）。"""

from __future__ import annotations

import json
from pathlib import Path

from agentic_rag.tools import file_tool as ft


def test_read_missing_file(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(ft.config, "PROJECT_ROOT", tmp_path)
    res = ft.read_file_content("no_such_file.txt", project_root=tmp_path)
    assert not res.ok
    assert "不存在" in (res.error or "")


def test_read_inside_project_uses_markitdown(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(ft.config, "PROJECT_ROOT", tmp_path)
    md_file = tmp_path / "note.md"
    md_file.write_text("# Hi\n\nbody", encoding="utf-8")
    res = ft.read_file_content(str(md_file), project_root=tmp_path)
    assert res.ok
    assert res.in_project_root
    assert res.backend == "markitdown"
    assert "Hi" in res.text


def test_format_read_response_schema():
    res = ft.FileReadResult(
        ok=True,
        path="/x/a.md",
        text="hello",
        suffix=".md",
        in_project_root=True,
        backend="markitdown",
    )
    raw = ft.format_file_read_response(res)
    payload = json.loads(raw)
    assert payload["schema_version"] == "topic4.tool.v1"
    assert payload["tool"] == "topic4_file_read"
    assert payload["data"]["text"] == "hello"


def test_ingest_empty_path(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(ft.config, "PROJECT_ROOT", tmp_path)
    out = ft.ingest_file_to_kb("", project_root=tmp_path)
    assert not out.get("ok")
