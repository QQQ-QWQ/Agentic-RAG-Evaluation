"""运行时入口分流单元测试。"""

from __future__ import annotations

import sys

from agentic_rag.runtime.entrypoints import cli_router


def test_fast_path_version():
    code = cli_router.try_fast_path(["--version"])
    assert code == 0


def test_fast_path_none_for_normal_argv():
    assert cli_router.try_fast_path(["chat", "-p", "hi"]) is None


def test_route_to_main_version(capsys):
    code = cli_router.route_to_main(["--version"])
    assert code == 0
    out = capsys.readouterr()
    assert "topic4 runtime" in out.out


def test_route_falls_back_to_topic4_help(monkeypatch, capsys):
    """非 runtime 子命令应动态导入既有 app.main。"""

    called: list[list[str]] = []

    def fake_main() -> None:
        called.append(list(sys.argv))
        raise SystemExit(0)

    monkeypatch.setattr("agentic_rag.cli.app.main", fake_main)
    code = cli_router.route_to_main(["--help"])
    assert code == 0
    assert called
