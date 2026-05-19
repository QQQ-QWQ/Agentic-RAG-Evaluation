"""第二层工具统一 JSON 输出外壳（便于 Agent 解析与日志）。"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "topic4.tool.v1"


def tool_response_json(
    tool: str,
    *,
    ok: bool,
    data: dict[str, Any] | None = None,
    error: str | None = None,
    hints: list[str] | None = None,
) -> str:
    payload = {
        "tool": tool,
        "schema_version": SCHEMA_VERSION,
        "ok": ok,
        "data": data or {},
        "error": error,
        "hints": hints or [],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
