"""
Topic4 RAG 管线预设（RunProfile），供「静态 CLI rag」与「Deep Agents 工具」共用。

与 C0/C1/C2 消融语义对齐：
  - ``c0_naive``：稠密检索，无改写、无混合。
  - ``c1_rewrite``：仅查询改写（关闭混合，便于对照 C1）。
  - ``c2_stage1_hybrid``：C1 + hybrid（稠密+BM25）。
  - ``c2_stage2_rerank``：再打开 LLM rerank。
  - ``c2_stage3_context``：再打开邻接块扩展（与仓库 C2 阶段 3 一致，邻居数可调）。
  - ``project_default``：与 ``RunProfile()`` 默认一致（等同 ``configs/run_default.yaml`` 思路）。
"""

from __future__ import annotations

from copy import deepcopy

from agentic_rag.experiment.profile import RunProfile

#: 预设 id -> 简短说明（给 Agent 与人类读）
RAG_PIPELINE_LABELS: dict[str, str] = {
    "project_default": "与工程默认 RunProfile 一致（Chroma + 混合 + C1 改写，可按 active_session 覆盖）",
    "c0_naive": "C0：无改写、无混合检索，仅稠密向量 Top-K",
    "c1_rewrite": "C1：查询改写 + 稠密检索（关闭混合，便于纯 C1 对照）",
    "c2_stage1_hybrid": "C2 阶段1：C1 + hybrid（稠密+BM25 融合）",
    "c2_stage2_rerank": "C2 阶段2：阶段1 + LLM rerank",
    "c2_stage3_context": "C2 阶段3：阶段2 + 邻接 chunk 上下文扩展",
}


def _base_c0() -> RunProfile:
    p = RunProfile()
    p.use_query_rewrite = False
    p.use_hybrid_retrieval = False
    p.use_rerank = False
    p.context_neighbor_chunks = 0
    return p


def _base_c1_only() -> RunProfile:
    p = RunProfile()
    p.use_query_rewrite = True
    p.use_hybrid_retrieval = False
    p.use_rerank = False
    p.context_neighbor_chunks = 0
    return p


def _base_c2_s1() -> RunProfile:
    p = RunProfile()
    p.use_query_rewrite = True
    p.use_hybrid_retrieval = True
    p.use_rerank = False
    p.context_neighbor_chunks = 0
    return p


def _base_c2_s2() -> RunProfile:
    p = _base_c2_s1()
    p.use_rerank = True
    return p


def _base_c2_s3() -> RunProfile:
    p = _base_c2_s2()
    p.context_neighbor_chunks = 1
    return p


def _base_project_default() -> RunProfile:
    """显式拷贝默认策略（与 dataclass 默认值一致）。"""
    return RunProfile()


_PRESET_BUILDERS: dict[str, RunProfile] = {
    "project_default": _base_project_default(),
    "c0_naive": _base_c0(),
    "c1_rewrite": _base_c1_only(),
    "c2_stage1_hybrid": _base_c2_s1(),
    "c2_stage2_rerank": _base_c2_s2(),
    "c2_stage3_context": _base_c2_s3(),
}


def list_preset_ids() -> list[str]:
    return list(_PRESET_BUILDERS.keys())


def run_profile_for_preset(preset_id: str) -> RunProfile:
    """返回一份 **拷贝**，避免 Agent 多轮调用互相污染同一 Profile。"""
    key = (preset_id or "").strip().lower()
    if key not in _PRESET_BUILDERS:
        valid = ", ".join(sorted(_PRESET_BUILDERS))
        raise ValueError(f"未知管线 preset={preset_id!r}，可选：{valid}")
    return deepcopy(_PRESET_BUILDERS[key])


def describe_presets() -> str:
    """供工具返回：人类可读的管线列表。"""
    lines = ["Topic4 RAG 管线（pipeline 参数取值）：", ""]
    for pid in sorted(_PRESET_BUILDERS):
        label = RAG_PIPELINE_LABELS.get(pid, "")
        lines.append(f"- {pid}: {label}")
    return "\n".join(lines)
