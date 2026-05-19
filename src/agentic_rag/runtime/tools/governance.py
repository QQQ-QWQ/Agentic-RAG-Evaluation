"""工具治理：注册、权限过滤、装配（封装既有 Topic4 工具）。"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from agentic_rag.runtime.state.app_state import PermissionState

ToolMode = Literal["simple", "full"]


@dataclass
class ToolSpec:
    name: str
    description: str
    enabled: bool = True


# C3 仅检索；C4 增加外部工具
_C3_NAMES = frozenset(
    {
        "topic4_list_rag_pipelines",
        "topic4_rag_query",
    }
)
_C4_EXTRA = frozenset(
    {
        "topic4_file_read",
        "topic4_file_ingest",
        "topic4_firecrawl_scrape",
        "topic4_firecrawl_search",
        "topic4_firecrawl_scrape_to_kb",
        "topic4_calculator",
        "topic4_table_analyzer",
        "topic4_code_runner",
        "sandbox_exec_python",
    }
)


def get_all_base_tool_specs(*, enable_c4: bool) -> list[ToolSpec]:
    from agentic_rag.tools.firecrawl_tool import firecrawl_configured

    specs = [
        ToolSpec("topic4_list_rag_pipelines", "列出 RAG 管线"),
        ToolSpec("topic4_rag_query", "知识库/单文档 RAG 问答"),
    ]
    if enable_c4:
        specs.extend(
            [
                ToolSpec("topic4_file_read", "读取本地文件（MarkItDown / parse_path）"),
                ToolSpec("topic4_file_ingest", "本地文件入库并重建 Chroma 索引"),
                ToolSpec("topic4_calculator", "安全算术表达式"),
                ToolSpec("topic4_table_analyzer", "CSV/TSV 统计"),
                ToolSpec("topic4_code_runner", "沙箱内 Python + 只读文件挂载"),
                ToolSpec("sandbox_exec_python", "沙箱内 Python（兼容别名）"),
            ]
        )
        if firecrawl_configured():
            specs.extend(
                [
                    ToolSpec("topic4_firecrawl_scrape", "Firecrawl 抓取 URL→Markdown"),
                    ToolSpec("topic4_firecrawl_search", "Firecrawl 网页搜索"),
                    ToolSpec("topic4_firecrawl_scrape_to_kb", "抓取网页并入库 Chroma"),
                ]
            )
    return specs


def filter_tools_by_deny_rules(
    tools: list[Any],
    *,
    permissions: PermissionState,
) -> list[Any]:
    denied = set(permissions.denied_tool_names)
    if not permissions.enable_c4_tools:
        denied |= _C4_EXTRA
    out: list[Any] = []
    for t in tools:
        name = getattr(t, "name", None) or str(t)
        if name in denied:
            continue
        if not permissions.enable_c4_tools and name not in _C3_NAMES:
            continue
        if name == "sandbox_exec_python" and not permissions.enable_sandbox:
            continue
        out.append(t)
    return out


def assemble_tool_pool(
    builtins: list[Any],
    *,
    extra: list[Any] | None = None,
    permissions: PermissionState,
) -> list[Any]:
    """过滤 → 去重（按 name）→ 稳定排序。"""
    merged = [*builtins, *(extra or [])]
    filtered = filter_tools_by_deny_rules(merged, permissions=permissions)
    by_name: dict[str, Any] = {}
    for t in filtered:
        name = getattr(t, "name", None) or repr(t)
        by_name[name] = t
    return [by_name[k] for k in sorted(by_name)]


def build_langchain_tools(
    *,
    doc_path: Path | None,
    sandbox_workspace: Path | None,
    permissions: PermissionState,
    use_knowledge_base: bool | None = None,
) -> list[Any]:
    from agentic_rag.deep_planning.tools_factory import build_topic4_rag_tools

    raw = build_topic4_rag_tools(
        doc_path,
        use_knowledge_base=use_knowledge_base,
        sandbox_workspace=sandbox_workspace if permissions.enable_c4_tools else None,
        enable_c4_tools=permissions.enable_c4_tools,
    )
    return assemble_tool_pool(raw, permissions=permissions)


def trace_tool_call(name: str, fn, *args, **kwargs) -> tuple[Any, dict[str, Any]]:
    """统一埋点：开始/结束/耗时。"""
    started = time.perf_counter()
    meta: dict[str, Any] = {"name": name, "ok": True, "error": ""}
    try:
        result = fn(*args, **kwargs)
        return result, meta
    except Exception as exc:
        meta["ok"] = False
        meta["error"] = str(exc)
        raise
    finally:
        meta["latency_ms"] = int((time.perf_counter() - started) * 1000)
