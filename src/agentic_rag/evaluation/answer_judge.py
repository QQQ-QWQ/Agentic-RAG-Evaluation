"""向后兼容：请优先使用 ``agentic_rag.evaluation.ai_answer_judge``。"""

from agentic_rag.evaluation.ai_answer_judge import (
    judge_answer_with_rule,
    load_judge_prompt_template,
)

__all__ = ["judge_answer_with_rule", "load_judge_prompt_template"]
