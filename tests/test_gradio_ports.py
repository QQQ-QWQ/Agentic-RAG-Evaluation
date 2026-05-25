"""Gradio 端口约定。"""

from __future__ import annotations

from agentic_rag.cli.gradio_launch import (
    DEFAULT_GRADIO_CLIENT_PORT,
    DEFAULT_GRADIO_LOGS_PORT,
    port_in_use,
)


def test_default_ports_differ():
    assert DEFAULT_GRADIO_CLIENT_PORT != DEFAULT_GRADIO_LOGS_PORT


def test_port_in_use_localhost():
    # 未监听的高端口通常可用
    assert port_in_use("127.0.0.1", 59999) is False
