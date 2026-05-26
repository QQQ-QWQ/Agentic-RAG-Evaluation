"""第二层 RAG 类工具调用配额（按编排轮次重置）。"""

from __future__ import annotations

import json
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from agentic_rag.deep_planning.tool_invoke_compat import coerce_for_tool_node

_quota_var: ContextVar["RagToolQuota | None"] = ContextVar("topic4_rag_tool_quota", default=None)
_session_quota_var: ContextVar["RagToolQuota | None"] = ContextVar(
    "topic4_rag_session_quota", default=None
)

RAG_TOOL_NAMES = frozenset(
    {
        "topic4_rag_query",
        "rag_subagent_c0",
        "rag_subagent_c1",
        "rag_subagent_c2",
        "rag_subagent_c3_lite",
    }
)


@dataclass
class RagToolQuota:
    max_calls: int
    count: int = 0
    blocked: list[str] = field(default_factory=list)
    block_duplicate_queries: bool = False
    seen_query_keys: set[str] = field(default_factory=set)
    duplicate_query_count: int = 0
    blocked_count: int = 0

    def try_consume(self, tool_name: str, tool_input: Any = None) -> str | None:
        """若超限返回错误 JSON 字符串；否则 None 表示允许调用。"""
        session = get_rag_session_quota()
        if session is not None and session.max_calls > 0:
            if session.count >= session.max_calls:
                session.blocked.append(tool_name)
                session.blocked_count += 1
                return json.dumps(
                    {
                        "error": "rag_session_quota_exceeded",
                        "tool": tool_name,
                        "max_total_calls": session.max_calls,
                        "hint": (
                            "本会话 RAG 总调用已达上限。请基于已有检索结果完成作答，"
                            "不要继续发起新检索。"
                        ),
                    },
                    ensure_ascii=False,
                )
            session.count += 1
        if self.block_duplicate_queries:
            key = _rag_query_key(tool_name, tool_input)
            if key:
                session_seen = session.seen_query_keys if session else set()
                if key in self.seen_query_keys or key in session_seen:
                    self.duplicate_query_count += 1
                    self.blocked_count += 1
                    if session:
                        session.duplicate_query_count += 1
                        session.blocked_count += 1
                        session.blocked.append(tool_name)
                    self.blocked.append(tool_name)
                    return json.dumps(
                        {
                            "error": "rag_duplicate_query_blocked",
                            "tool": tool_name,
                            "hint": (
                                "本轮已检索过高度相同的问题。请基于已有证据作答，"
                                "不要继续重复检索。"
                            ),
                        },
                        ensure_ascii=False,
                    )
                self.seen_query_keys.add(key)
                if session:
                    session.seen_query_keys.add(key)
        if self.max_calls <= 0:
            return None
        if self.count >= self.max_calls:
            self.blocked.append(tool_name)
            self.blocked_count += 1
            return json.dumps(
                {
                    "error": "rag_tool_quota_exceeded",
                    "tool": tool_name,
                    "max_calls": self.max_calls,
                    "hint": (
                        "本编排轮次 RAG 调用已达上限。请基于已有检索结果作答，"
                        "勿再并行发起新检索；勿调用 topic4_list_rag_pipelines。"
                    ),
                },
                ensure_ascii=False,
            )
        self.count += 1
        return None


def set_rag_tool_quota(quota: RagToolQuota | None) -> None:
    _quota_var.set(quota)


def get_rag_tool_quota() -> RagToolQuota | None:
    return _quota_var.get()


def reset_rag_tool_quota(
    *,
    max_calls: int,
    block_duplicate_queries: bool = False,
) -> RagToolQuota:
    q = RagToolQuota(
        max_calls=max(0, int(max_calls)),
        block_duplicate_queries=block_duplicate_queries,
    )
    set_rag_tool_quota(q)
    return q


def get_rag_session_quota() -> RagToolQuota | None:
    return _session_quota_var.get()


def reset_rag_session_quota(
    *,
    max_total_calls: int,
    block_duplicate_queries: bool = False,
) -> RagToolQuota | None:
    """整次用户回合 RAG 总上限；``max_total_calls<=0`` 表示不限制。"""
    total = max(0, int(max_total_calls))
    if total <= 0 and not block_duplicate_queries:
        set_rag_session_quota(None)
        return None
    q = RagToolQuota(
        max_calls=total,
        block_duplicate_queries=block_duplicate_queries,
    )
    set_rag_session_quota(q)
    return q


def set_rag_session_quota(quota: RagToolQuota | None) -> None:
    _session_quota_var.set(quota)


def wrap_tools_with_rag_quota(tools: list[Any]) -> list[Any]:
    """仅包装 RAG 类工具，超限时返回 JSON 错误而非抛异常。"""
    out: list[Any] = []
    for tool in tools:
        name = getattr(tool, "name", None) or getattr(tool, "__name__", "")
        if name not in RAG_TOOL_NAMES:
            out.append(tool)
            continue
        if getattr(tool, "_topic4_quota_wrapped", False):
            out.append(tool)
            continue

        original_invoke = tool.invoke
        original_ainvoke = getattr(tool, "ainvoke", None)

        def invoke(
            input: Any,
            config: Any = None,
            *,
            _orig_invoke=original_invoke,
            _name: str = name,
            **kwargs: Any,
        ) -> Any:
            quota = get_rag_tool_quota()
            if quota is not None:
                block = quota.try_consume(_name, input)
                if block is not None:
                    return coerce_for_tool_node(block, input, _name)
            if config is not None:
                result = _orig_invoke(input, config=config, **kwargs)
            else:
                result = _orig_invoke(input, **kwargs)
            return coerce_for_tool_node(result, input, _name)

        async def ainvoke(
            input: Any,
            config: Any = None,
            *,
            _orig_ainvoke=original_ainvoke,
            _name: str = name,
            **kwargs: Any,
        ) -> Any:
            if _orig_ainvoke is None:
                return invoke(
                    input,
                    config,
                    _orig_invoke=original_invoke,
                    _name=_name,
                    **kwargs,
                )
            quota = get_rag_tool_quota()
            if quota is not None:
                block = quota.try_consume(_name, input)
                if block is not None:
                    return coerce_for_tool_node(block, input, _name)
            if config is not None:
                result = await _orig_ainvoke(input, config=config, **kwargs)
            else:
                result = await _orig_ainvoke(input, **kwargs)
            return coerce_for_tool_node(result, input, _name)

        object.__setattr__(tool, "invoke", invoke)
        if original_ainvoke is not None:
            object.__setattr__(tool, "ainvoke", ainvoke)
        object.__setattr__(tool, "_topic4_quota_wrapped", True)
        out.append(tool)
    return out


def _rag_query_key(tool_name: str, tool_input: Any) -> str:
    """Return a conservative duplicate key; avoid fuzzy blocking that hurts recall."""
    if tool_name not in RAG_TOOL_NAMES:
        return ""
    pipeline = ""
    question = ""
    if isinstance(tool_input, dict):
        pipeline = str(tool_input.get("pipeline") or tool_name).strip().lower()
        question = str(tool_input.get("question") or tool_input.get("__arg1") or "").strip()
    else:
        pipeline = tool_name
        question = str(tool_input or "").strip()
    q = " ".join(question.lower().split())
    q = q.strip(" \t\r\n，。！？,.!?;；：:")
    return f"{tool_name}|{pipeline}|{q}" if q else ""
