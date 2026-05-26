"""将固定管线的 RAG 检索注册为子 Agent 工具（减少选管线 + 重复 list 调用）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from agentic_rag.deep_planning.rag_executor import execute_topic4_rag

# (tool_name, pipeline_id, 给 Lead Agent 的说明)
RAG_SUBAGENT_SPECS: tuple[tuple[str, str, str], ...] = (
    (
        "rag_subagent_c0",
        "c0_naive",
        "【C0 检索子代理】稠密向量 Top-K，无改写/混合。适合定义型、单点事实题；"
        "简单题通常 1 次即可；若证据不足可再调 c2 或其它子 Agent（串行，勿并行刷同一问）。",
    ),
    (
        "rag_subagent_c1",
        "c1_rewrite",
        "【C1 检索子代理】查询改写 + 稠密检索。适合表述模糊、需改写对齐的题；"
        "模糊题可先本 Agent；仍不足可串行换 c2，勿对同一问并行多次。",
    ),
    (
        "rag_subagent_c2",
        "c2_stage3_context",
        "【C2 检索子代理】混合检索 + rerank + 邻接上下文扩展。适合多证据、对比、综述题；"
        "多证据/对比题优先；同一问可串行 2–3 次检索。禁止把多道小题塞进一次 tool 并行调用。",
    ),
    (
        "rag_subagent_c3_lite",
        "c3_lite_v2",
        "【C3-lite 检索子代理】多查询 RRF 融合 + rerank + Evidence Grader；"
        "适合 fuzzy_query、multi_doc 和需要更稳引用的复杂知识题。",
    ),
)

SUBAGENT_TOOL_NAMES = frozenset(name for name, _, _ in RAG_SUBAGENT_SPECS)


def build_rag_subagent_tools(
    *,
    doc_path: str | Path | None = None,
    use_knowledge_base: bool | None = None,
    kb_doc_ids: list[str] | None = None,
    compact_max_chars: int = 12_000,
    evidence_max_chars: int = 6000,
) -> list[Any]:
    """为第二层 Lead Agent 注册固定管线的检索子 Agent（LangChain Tool）。"""
    tools: list[Any] = []

    for tool_name, pipeline_id, description in RAG_SUBAGENT_SPECS:

        def _make_fn(
            _name: str = tool_name,
            _pipeline: str = pipeline_id,
            _desc: str = description,
            _doc_path=doc_path,
            _use_kb=use_knowledge_base,
            _kb_ids=kb_doc_ids,
            _max: int = compact_max_chars,
            _ev_max: int = evidence_max_chars,
        ):
            def _rag_subagent(question: str) -> str:
                """对知识库执行一次固定管线 RAG；参数仅 question。"""
                return execute_topic4_rag(
                    question,
                    _pipeline,
                    doc_path=_doc_path,
                    use_knowledge_base=_use_kb,
                    kb_doc_ids=_kb_ids,
                    compact_max_chars=_max,
                    evidence_max_chars=_ev_max,
                    via_subagent=True,
                )

            _rag_subagent.__name__ = _name
            _rag_subagent.__doc__ = _desc
            return tool(_rag_subagent)

        tools.append(_make_fn())

    return tools
