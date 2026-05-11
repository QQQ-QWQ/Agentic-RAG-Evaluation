"""
Deep Agents 动态规划分支（可选依赖）。

- **静态管线**：继续使用 ``main.py rag`` / ``experiment``，与既有 C0–C2 完全一致。
- **双层级**：
    - **第一层**（``session_planner``）：对用户自然语言做意图与路径抽取，输出 JSON 规划；
    - **第二层**（``create_deep_agent``）：挂载 ``topic4_rag_query``，默认 ``run_knowledge_base_rag``（Chroma 全库），绑单文档时用 ``run_document_rag``。

安装::

    uv sync --group agent

入口::

    uv run python main.py agent              # 先输入一段自然语言（可含路径+任务）
    uv run python main.py agent [PATH] --once \"一段话\"

公开符号（轻依赖）::

    from agentic_rag.deep_planning.presets import describe_presets, run_profile_for_preset
"""

from agentic_rag.deep_planning.presets import (
    RAG_PIPELINE_LABELS,
    describe_presets,
    list_preset_ids,
    run_profile_for_preset,
)

__all__ = [
    "RAG_PIPELINE_LABELS",
    "describe_presets",
    "list_preset_ids",
    "run_profile_for_preset",
]
