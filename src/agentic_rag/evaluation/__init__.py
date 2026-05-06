"""评测辅助（含独立 AI 评判子包 ``ai_answer_judge``）。"""

from agentic_rag.evaluation.ai_answer_judge import judge_answer_with_rule

__all__ = ["judge_answer_with_rule"]
