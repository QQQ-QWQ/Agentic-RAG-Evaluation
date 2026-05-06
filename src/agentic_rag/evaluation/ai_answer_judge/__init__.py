"""
独立子模块：**AI 评判（LLM-as-judge）**，按 ``references.csv`` 的 ``judge_rule`` 打分。

用途：

- 在实验流水线中对生成答案做 **自动化测试输出**（非最终金标准）；
- 预留与 **人工标注** 对比，用于评估「AI 评判」及后续「AI 自规划 / 自检」环节的可信度。

脚本入口（仓库根）：``run_score_answer_accuracy.py``、``run_c2_ablation_answer_accuracy.py``。
"""

from agentic_rag.evaluation.ai_answer_judge.judge import (
    judge_answer_with_rule,
    load_judge_prompt_template,
)

__all__ = ["judge_answer_with_rule", "load_judge_prompt_template"]
