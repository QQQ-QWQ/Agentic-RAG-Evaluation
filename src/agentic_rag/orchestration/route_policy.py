"""
按测试集元数据与题型选择执行路径，避免简单题走完整 C3 编排。

路径说明：
- ``c2_kb``：单次全库 RAG（C0/C1/C2 预设），无 L1/L2/L3 编排。
- ``c3_orchestrated`` / ``c4_orchestrated``：完整 Topic4 三层编排。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ExecutionMode = Literal["c2_kb", "c3_orchestrated", "c4_orchestrated"]


@dataclass(frozen=True)
class RouteDecision:
    mode: ExecutionMode
    rag_preset: str
    reason: str
    max_orchestration_rounds: int | None = None
    max_execute_retries_per_round: int | None = None
    max_rag_tool_calls_per_round: int | None = None
    max_total_rag_calls: int | None = None
    prefer_complete_when_grounded: bool = True


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def resolve_route(
    *,
    task_type: str = "",
    difficulty: str = "",
    expected_path: str = "",
    required_tool: str = "",
    tier: str = "c3",
    enable_adaptive_routing: bool = True,
) -> RouteDecision:
    """
    解析单题执行路径。

    优先 ``expected_path``（questions.csv），再结合 ``task_type`` / ``required_tool`` / ``tier``。
    ``enable_adaptive_routing=False`` 时：c3→完整 C3，c4→完整 C4。
    """
    tier_n = _norm(tier) or "c3"
    if not enable_adaptive_routing:
        if tier_n == "c4":
            return RouteDecision(
                mode="c4_orchestrated",
                rag_preset="c2_stage2_rerank",
                reason="adaptive_disabled_tier_c4",
                max_orchestration_rounds=4,
                max_execute_retries_per_round=2,
                max_rag_tool_calls_per_round=10,
            )
        return RouteDecision(
            mode="c3_orchestrated",
            rag_preset="c2_stage2_rerank",
            reason="adaptive_disabled_tier_c3",
            max_orchestration_rounds=4,
            max_execute_retries_per_round=2,
            max_rag_tool_calls_per_round=10,
        )

    exp = (expected_path or "").strip().upper()
    tool = _norm(required_tool)
    tt = _norm(task_type)
    diff = _norm(difficulty)

    def c2(preset: str, reason: str) -> RouteDecision:
        return RouteDecision(
            mode="c2_kb",
            rag_preset=preset,
            reason=reason,
        )

    def c3_light(reason: str) -> RouteDecision:
        return RouteDecision(
            mode="c3_orchestrated",
            rag_preset="c2_stage2_rerank",
            reason=reason,
            max_orchestration_rounds=2,
            max_execute_retries_per_round=1,
            max_rag_tool_calls_per_round=4,
            max_total_rag_calls=8,
        )

    def c3_full(reason: str) -> RouteDecision:
        return RouteDecision(
            mode="c3_orchestrated",
            rag_preset="c2_stage2_rerank",
            reason=reason,
            max_orchestration_rounds=4,
            max_execute_retries_per_round=2,
            max_rag_tool_calls_per_round=10,
            max_total_rag_calls=24,
        )

    def c4_full(reason: str) -> RouteDecision:
        return RouteDecision(
            mode="c4_orchestrated",
            rag_preset="c2_stage2_rerank",
            reason=reason,
            max_orchestration_rounds=4,
            max_execute_retries_per_round=2,
            max_rag_tool_calls_per_round=10,
            max_total_rag_calls=24,
        )

    # 工具题：C4 档位走完整 C4；C3 档位仍用 C2 单次检索（避免空转），日志提示应使用 --tier c4
    if tool and tool != "none":
        if tier_n == "c4":
            return c4_full("required_tool_tier_c4")
        return c2(
            "c2_stage2_rerank",
            "tool_task_on_c3_tier_fallback_c2_kb",
        )

    if exp == "C0":
        return c2("c0_naive", "expected_path_c0")
    if exp == "C1":
        return c2("c1_rewrite", "expected_path_c1")
    if exp == "C2":
        return c2("c2_stage2_rerank", "expected_path_c2")
    if exp == "C4":
        if tier_n == "c4":
            return c4_full("expected_path_c4")
        return c2("c2_stage2_rerank", "expected_path_c4_on_c3_tier_fallback_c2_kb")
    if exp == "C3":
        return c3_full("expected_path_c3")

    # 无 expected_path：按题型启发
    if tt == "simple_qa":
        return c2("c0_naive" if diff == "easy" else "c2_stage2_rerank", "task_type_simple_qa")

    if tt in ("calculation", "table_analysis", "code_execution"):
        if tier_n == "c4":
            return c4_full(f"task_type_{tt}_tier_c4")
        return c2("c2_stage2_rerank", f"task_type_{tt}_tier_c3_c2_kb")

    if tt == "multi_doc":
        if diff == "hard":
            return c3_full("task_type_multi_doc_hard")
        return c3_light("task_type_multi_doc")

    if tt == "fuzzy_query":
        if diff == "hard":
            return c3_light("task_type_fuzzy_query_hard")
        return c2("c1_rewrite", "task_type_fuzzy_query")

    if tt == "insufficient_evidence":
        return c3_light("task_type_insufficient_evidence")

    if tier_n == "c4":
        return c4_full("default_tier_c4")
    return c2("c2_stage2_rerank", "default_c2_kb")


def apply_route_to_orchestration(
    config: Any,
    route: RouteDecision,
    *,
    tier: str = "c3",
) -> Any:
    """将 ``RouteDecision`` 中的预算写入 ``OrchestrationConfig``（原地修改并返回）。"""
    from agentic_rag.orchestration.types import OrchestrationConfig

    if not isinstance(config, OrchestrationConfig):
        return config
    if route.max_orchestration_rounds is not None:
        config.max_orchestration_rounds = max(1, int(route.max_orchestration_rounds))
    if route.max_execute_retries_per_round is not None:
        config.max_execute_retries_per_round = max(
            1, int(route.max_execute_retries_per_round)
        )
    if route.max_rag_tool_calls_per_round is not None:
        config.max_rag_tool_calls_per_round = max(
            0, int(route.max_rag_tool_calls_per_round)
        )
    if route.max_total_rag_calls is not None:
        config.max_total_rag_calls = max(0, int(route.max_total_rag_calls))
    config.prefer_complete_when_grounded = route.prefer_complete_when_grounded
    tier_n = _norm(tier) or "c3"
    if route.mode == "c4_orchestrated":
        config.enable_c4_tools = True
    elif route.mode == "c3_orchestrated":
        config.enable_c4_tools = tier_n == "c4"
    return config
