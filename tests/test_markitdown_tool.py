from __future__ import annotations

from pathlib import Path

from agentic_rag.tools.markitdown_tool import convert_local_file_to_markdown_safe


def test_markitdown_safe_rejects_outside_project(tmp_path: Path) -> None:
    inner = tmp_path / "proj"
    inner.mkdir()
    outside = tmp_path / "evil.md"
    outside.write_text("# x", encoding="utf-8")
    r = convert_local_file_to_markdown_safe(outside, project_root=inner)
    assert r.error
    assert "工程根" in r.error or "内" in r.error


def test_markitdown_safe_converts_markdown_file(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text("# Title\n\nbody", encoding="utf-8")
    r = convert_local_file_to_markdown_safe(f, project_root=tmp_path)
    assert r.error is None
    assert "Title" in r.text
