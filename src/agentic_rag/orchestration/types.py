"""多层级编排共用数据结构（与评测 judge 无关）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

VerdictCode = Literal["complete", "continue_execute", "replan", "need_user_input"]


@dataclass
class OrchestrationConfig:
    """编排循环参数；可在入口或 Registry 中替换/扩展。"""

    max_orchestration_rounds: int = 4
    """外层「规划→执行→研判」循环上限（含重规划）。"""
    max_execute_retries_per_round: int = 2
    """同一轮规划下，研判要求「继续执行」时对第二层的最大追加调用次数。"""
    enable_judge: bool = True
    """关闭则只做规划+执行（兼容快速调试）。"""
    judge_temperature: float = 0.12
    planner_temperature: float = 0.15
    orchestrate_follow_ups: bool = False
    """若为 True，后续用户每一轮输入都走完整编排（成本高）。"""
    enable_kb_grounding_judge: bool = True
    """参照评测 judge 思路：用检索摘录与模型答复做「有据」核验，供第三层参考。"""
    enable_c4_tools: bool = False
    """C3/C4 档位开关：False 仅启用检索工具，True 启用 C4 外部工具。"""
    enable_sandbox_tools: bool = True
    """为 True 且 ``SANDBOX_ENABLED`` 时挂载 ``sandbox_exec_python``（会话临时目录）。"""
    enable_planning_query_rewrite: bool = False
    """为 True 时在第一层前调用与 C1 同源的 ``rewrite_query``，将检索导向摘要注入规划上下文（多一次 DeepSeek）。"""
    planning_rewrite_prompt_file: Path | None = None
    """改写提示词；默认 ``<PROJECT_ROOT>/prompts/query_rewrite_prompt.md``（由调用方解析）。"""
    enable_kb_inventory_hints: bool = True
    """为 True 时在第二层消息中附加 ``documents.csv`` 登记状态（确定性事实，非模型猜测）。"""
    use_rag_subagent_tools: bool = True
    """为 True 时第二层用 ``rag_subagent_c0/c1/c2`` 固定管线子 Agent，减少选参与 list 调用。"""
    max_rag_tool_calls_per_round: int = 10
    """单轮第二层执行中 RAG 类工具（含子 Agent）最大调用次数；0 表示不限制。"""
    max_total_rag_calls: int = 0
    """整次用户回合内 RAG 调用总上限；0 表示仅按每轮上限。"""
    enable_adaptive_routing: bool = True
    """批量/入口侧按题型与 expected_path 选择 C2 轻路径或 C3/C4 编排（见 route_policy）。"""
    prefer_complete_when_grounded: bool = True
    """第三层：证据已对齐且执行轮次已用尽一次时，倾向 complete 而非继续检索。"""


@dataclass
class JudgeVerdict:
    """第三层研判（结构化）。"""

    verdict: VerdictCode
    summary_for_user: str
    hint_for_next_planner: str | None
    hint_for_next_execution: str | None
    reasoning_brief: str
    raw: dict[str, Any] = field(default_factory=dict)


def verdict_from_json(data: dict[str, Any]) -> JudgeVerdict:
    """容错解析模型 JSON。"""
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                data = item
                break
        else:
            data = {}
    if not isinstance(data, dict):
        data = {}
    v = str(data.get("verdict") or data.get("decision") or "complete").strip().lower()
    mapping: dict[str, VerdictCode] = {
        "complete": "complete",
        "done": "complete",
        "finish": "complete",
        "continue_execute": "continue_execute",
        "continue": "continue_execute",
        "retry_execution": "continue_execute",
        "replan": "replan",
        "re_plan": "replan",
        "need_user_input": "need_user_input",
        "ask_user": "need_user_input",
        "clarify": "need_user_input",
    }
    verdict: VerdictCode = mapping.get(v, "complete")
    return JudgeVerdict(
        verdict=verdict,
        summary_for_user=str(data.get("summary_for_user") or data.get("user_summary") or "").strip(),
        hint_for_next_planner=_none_if_empty(data.get("hint_for_next_planner")),
        hint_for_next_execution=_none_if_empty(data.get("hint_for_next_execution")),
        reasoning_brief=str(data.get("reasoning_brief") or "").strip(),
        raw=data,
    )


def _none_if_empty(x: Any) -> str | None:
    if x is None:
        return None
    s = str(x).strip()
    return s if s else None
