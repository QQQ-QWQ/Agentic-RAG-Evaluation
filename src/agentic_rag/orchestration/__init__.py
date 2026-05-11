"""
多层级编排：规划 → 执行（Deep Agent + Topic4 工具）→ 研判 → 可扩展分支。

- ``OrchestrationConfig`` / ``OrchestrationHooks``：参数与回调扩展点。
- ``run_cli_agent_session``：``main.py agent`` 的实际入口逻辑。

示例（程序化扩展）::

    from pathlib import Path
    from agentic_rag.orchestration import OrchestrationConfig, run_cli_agent_session

    run_cli_agent_session(
        cli_doc=Path(\"doc.md\"),
        skip_layer1=False,
        once_text=\"请总结第三节\",
        temperature=0.35,
        json_debug=False,
        config=OrchestrationConfig(max_orchestration_rounds=6),
    )
"""

from agentic_rag.orchestration.loop import run_cli_agent_session
from agentic_rag.orchestration.registry import OrchestrationHooks
from agentic_rag.orchestration.types import OrchestrationConfig, JudgeVerdict

__all__ = [
    "JudgeVerdict",
    "OrchestrationConfig",
    "OrchestrationHooks",
    "run_cli_agent_session",
]
