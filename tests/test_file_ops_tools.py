"""C4 写盘 / 编辑 / shell 工具测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentic_rag.tools.file_tool import edit_file_content, write_file_content
from agentic_rag.tools.path_policy import assert_write_path_allowed, is_shell_command_allowed
from agentic_rag.tools.shell_tool import run_shell_in_workspace


def test_write_denies_env(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("x=1", encoding="utf-8")
    with pytest.raises(PermissionError):
        assert_write_path_allowed(".env")


def test_write_and_edit_under_runs(tmp_path, monkeypatch):
    from agentic_rag import config

    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)

    target = "runs/agent_test/note.txt"
    w = write_file_content(target, "hello\nworld\n", project_root=tmp_path)
    assert w.ok is True
    assert (tmp_path / target).read_text(encoding="utf-8") == "hello\nworld\n"

    e = edit_file_content(
        target,
        "world",
        "WORLD",
        project_root=tmp_path,
    )
    assert e.ok is True
    assert (tmp_path / target).read_text(encoding="utf-8") == "hello\nWORLD\n"


def test_shell_blocks_rm_rf():
    ok, _ = is_shell_command_allowed("rm -rf /")
    assert ok is False


def test_shell_echo(tmp_path):
    payload = run_shell_in_workspace(
        'Write-Output "ok"' if __import__("sys").platform == "win32" else 'echo ok',
        tmp_path,
        timeout_sec=30,
    )
    assert payload.get("exit_code") == 0
    assert "ok" in (payload.get("stdout") or "")


def test_c4_file_ops_registered(monkeypatch):
    monkeypatch.setenv("FILE_WRITE_ENABLED", "true")
    monkeypatch.setenv("SHELL_COMMAND_ENABLED", "true")
    from agentic_rag import config

    monkeypatch.setattr(config, "FILE_WRITE_ENABLED", True)
    monkeypatch.setattr(config, "SHELL_COMMAND_ENABLED", True)

    from agentic_rag.deep_planning.tools_factory import build_topic4_rag_tools

    names = {getattr(t, "name", "") for t in build_topic4_rag_tools(enable_c4_tools=True)}
    assert "topic4_file_write" in names
    assert "topic4_file_edit" in names
    assert "topic4_shell_exec" in names
