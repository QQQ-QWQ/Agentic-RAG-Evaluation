# AI 评判模块（LLM-as-judge）

本文档说明独立包 **`agentic_rag.evaluation.ai_answer_judge`** 的定位与输出字段，与 `docs/interface_and_logging_rules.md`、题库字段对齐。

## 1. 定位（不等于最终正确性）

- **作用**：在实验流水线中，按 `data/testset/references.csv` 的 **`judge_rule`**，由 DeepSeek 对 **`answer`** 打 **0 / 0.5 / 1**，便于批量回归与阶段对比。
- **不是**：经人工复核后的「标准答案是否正确」终裁；表中数值属于 **自动化测试结果**。
- **后续**：人工按同一 `judge_rule` 标注后，与 AI 分数对齐（一致性 / Cohen's κ 等），用于评估 **AI 评判**及后续 **AI 自规划 / 自检** 链路的可信度。

## 2. 代码入口

| 入口 | 说明 |
| --- | --- |
| `src/agentic_rag/evaluation/ai_answer_judge/` | 核心：`judge_answer_with_rule()` |
| `prompts/answer_judge_prompt.md` | 评判 Prompt 模板 |
| `run_score_answer_accuracy.py` | 单份结果 CSV → `*_scored.csv` |
| `run_c2_ablation_answer_accuracy.py` | C2 三阶段批量评判 + 汇总 JSON/Markdown |

兼容导入：`from agentic_rag.evaluation.answer_judge import judge_answer_with_rule`（转发到新包）。

## 3. 单次评判输出（字典）

| 字段 | 含义 |
| --- | --- |
| `correctness_score` | `0` / `0.5` / `1`，与题库规则一致 |
| `correctness_label` | `wrong` / `partial` / `correct` |
| `judge_reason` | 评判模型给出的简短理由 |
| `judge_total_tokens` | 本次评判 API `usage.total_tokens` |

## 4. 写入 CSV 的扩展列（`*_scored.csv`）

在原始结果列之后追加：`correctness_score`、`correctness_label`、`judge_reason`、`judge_skipped`、`judge_total_tokens`。

后续人工标注可增加列，例如：`human_score`、`human_note`，用于与 `correctness_score` 对比。

## 5. 与实验记录的关系

完整实验结论须结合 `docs/experiment_notes.md` 中说明：**当前呈现的 AI 正确率为流水线上的测试结果，正确性以待后续人工标注验证。**
