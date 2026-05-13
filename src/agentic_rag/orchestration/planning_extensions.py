"""
规划阶段可扩展钩子：查询改写注入、知识库登记事实备注等。

后续若要增加「意图分类器」「规则填槽」等，优先通过：

- ``OrchestrationHooks.planning_context_enricher`` 返回附加文本；或
- 在本模块增加纯函数，并在 ``loop._orchestrate_until_stable`` 中按配置串联。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from agentic_rag.experiment.kb_inventory import (
    file_path_registered_in_documents_csv,
    relative_path_under_project,
)
from agentic_rag.schemas import RewriteResult


@dataclass(frozen=True)
class PlanningEnrichInput:
    """供自定义 ``planning_context_enricher`` 使用的上下文（可随需扩展字段）。"""

    user_natural_language: str
    cli_document_path: str | None
    project_root: Path
    orchestration_round: int


class PlanningContextEnricher(Protocol):
    """规划前向第一层追加上下文的扩展点。"""

    def __call__(self, inp: PlanningEnrichInput) -> str | None: ...


def format_query_rewrite_block(rr: RewriteResult) -> str:
    """将 C1 同源 ``rewrite_query`` 结果格式化为第一层可读块。"""
    lines = [
        "【查询改写·辅助规划（与批量 C1 同源 rewrite 模块）】",
        f"- need_rewrite: {rr.need_rewrite}",
        f"- rewrite_type: {rr.rewrite_type}",
        f"- rewrite_confidence: {rr.rewrite_confidence:.2f}",
    ]
    if rr.rewrite_reason:
        lines.append(f"- rewrite_reason: {rr.rewrite_reason}")
    lines.append(f"- 检索导向主 query: {rr.rewritten_query}")
    if rr.rewritten_queries:
        lines.append("- 多候选检索 query:")
        for i, q in enumerate(rr.rewritten_queries[:6], start=1):
            lines.append(f"  {i}. {q}")
    lines.append(
        "（以上仅供你理解用户意图与检索方向；第一层仍须自行输出 JSON 规划，不要复述改写 JSON。）"
    )
    return "\n".join(lines)


def kb_execution_notes_for_layer2(
    *,
    project_root: Path,
    doc_resolved: Path | None,
    plan_document_path_str: str | None,
    kb_mutation_intent: str,
) -> str:
    """
    第二层系统备注：以 ``documents.csv`` 为准的登记状态 + 第一层入库意图摘要。

    说明：「已向量化」在工程语义上 = 已登记且后续 ``kb_index_builder`` 指纹命中 Chroma；
    此处仅给出 **清单是否登记**，避免模型臆测。
    """
    intent = (kb_mutation_intent or "none").strip().lower()
    lines = [
        f"- 第一层声明的入库意图 kb_mutation_intent: {intent}",
    ]
    if doc_resolved is not None and doc_resolved.is_file():
        reg = file_path_registered_in_documents_csv(project_root, doc_resolved)
        rel = relative_path_under_project(project_root, doc_resolved)
        rel_s = rel or str(doc_resolved)
        if reg:
            lines.append(
                f"- 单文件 `{rel_s}` **已在** `documents.csv` 中登记。"
                "若用户仅检索/问答，一般 **无需** 再调 `topic4_kb_ingest`；"
                "除非用户明确要求更新文档或替换清单行。"
            )
        else:
            lines.append(
                f"- 单文件 `{rel_s}` **未在** `documents.csv` 中登记。"
                "若需纳入全库向量索引，可调用 `topic4_kb_ingest`（路径须在工程根内）。"
            )
    elif plan_document_path_str and str(plan_document_path_str).strip():
        p = str(plan_document_path_str).strip()
        lines.append(
            f"- 第一层给出路径字符串 `{p}`，但系统侧 **未能解析为存在的本地文件**。"
            "请结合工具与用户原文核对路径，必要时追问。"
        )
    else:
        lines.append(
            "- 未绑定单文件路径；默认使用工程 **Chroma 全库**（由 `documents.csv` 定义文档集合）。"
        )
    return "\n".join(lines)
