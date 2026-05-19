"""系统知识库 sync / 路径规则单测。"""

from __future__ import annotations

from pathlib import Path

from agentic_rag.experiment.kb_paths import (
    is_excluded_from_system_sync,
    iter_system_raw_files,
)


def test_excluded_dirs():
    assert is_excluded_from_system_sync("data/raw/session_upload/x.md")
    assert is_excluded_from_system_sync("data/raw/user_docs/a.pdf")
    assert not is_excluded_from_system_sync("data/raw/tech_docs/a.md")


def test_iter_system_raw_files_project(tmp_path: Path, monkeypatch):
    root = tmp_path
    (root / "data" / "raw" / "tech_docs").mkdir(parents=True)
    (root / "data" / "raw" / "session_upload").mkdir(parents=True)
    f1 = root / "data" / "raw" / "tech_docs" / "a.md"
    f1.write_text("# hi", encoding="utf-8")
    (root / "data" / "raw" / "session_upload" / "b.md").write_text("no", encoding="utf-8")
    monkeypatch.chdir(root)
    from agentic_rag import config

    monkeypatch.setattr(config, "PROJECT_ROOT", root)
    found = iter_system_raw_files(root)
    assert len(found) == 1
    assert found[0].name == "a.md"
