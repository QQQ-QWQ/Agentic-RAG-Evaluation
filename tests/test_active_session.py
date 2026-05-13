from __future__ import annotations

from pathlib import Path

from agentic_rag.experiment.active_session import apply_active_session
from agentic_rag.experiment.profile import RunProfile


def test_apply_active_session_overrides_default(tmp_path: Path) -> None:
    p = tmp_path / "active_session.yaml"
    p.write_text(
        "schema_version: 1\nuse_query_rewrite: false\ntop_k: 3\n",
        encoding="utf-8",
    )
    profile = RunProfile()
    assert profile.use_query_rewrite is True
    assert apply_active_session(profile, p) is True
    assert profile.use_query_rewrite is False
    assert profile.top_k == 3


def test_apply_active_session_missing_file(tmp_path: Path) -> None:
    profile = RunProfile()
    assert apply_active_session(profile, tmp_path / "nope.yaml") is False
