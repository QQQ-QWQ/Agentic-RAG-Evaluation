"""Shared Gradio launch helpers."""

from __future__ import annotations

import socket

DEFAULT_GRADIO_CLIENT_PORT = 7860
DEFAULT_GRADIO_LOGS_PORT = 7861


def port_in_use(host: str, port: int, *, timeout: float = 0.2) -> bool:
    """Return True when a TCP port accepts connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, int(port))) == 0
