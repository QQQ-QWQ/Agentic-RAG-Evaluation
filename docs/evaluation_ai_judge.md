# AI 评判模块（LLM-as-judge）

本文档说明独立包 **`agentic_rag.evaluation.ai_answer_judge`** 的定位、评分维度和输出字段。AI Judge 是项目原定的自动化辅助评测机制，可以在实验结果中保留；但它不等同于最终人工评分。`codex_precheck` 只作为组长个人临时辅助判断，不进入正式实验记录。

## 1. 定位

- **可以保留**：AI Judge 评分属于实验流水线的一部分，可用于批量回归、阶段对比和发现可疑样例。
- **不能替代人工**：正式结论仍以人工评分、失败案例分析和指标表为准。
- **使用方式**：先用 AI Judge 批量打分，再由人工重点复核低分题、冲突题和关键结论题。
- **适用范围**：适合评估答案质量、完整性、引用支撑和证据一致性；不适合单独作为论文式最终结论。

## 2. 两套评分入口

| 模式 | 函数 / 脚本 | 作用 | 输出文件 |
| --- | --- | --- | --- |
| 旧版答案正确率评分 | `judge_answer_with_rule()` / `run_score_answer_accuracy.py` | 只按 `judge_rule` 给 `answer` 打 `0 / 0.5 / 1` | `*_scored.csv` |
| C2 三阶段答案正确率 | `run_c2_ablation_answer_accuracy.py` | 对 C2 stage1/2/3 统一跑旧版答案正确率评分 | `c2_ablation_answer_accuracy.*` |
| 新版多维 RAG 评分 | `judge_rag_response_with_rubric()` / `run_score_rag_multidim.py` | 同时评估答案、完整性、引用和证据一致性 | `*_llm_judged.csv` |

兼容导入：

```python
from agentic_rag.evaluation.answer_judge import (
    judge_answer_with_rule,
    judge_rag_response_with_rubric,
)
```

## 3. 多维评分内容

所有维度统一使用 `0 / 0.5 / 1`：

| 维度 | 字段 | 评分含义 |
| --- | --- | --- |
| 答案正确性 | `answer_correctness_score` | 是否符合参考答案和该题 `judge_rule` |
| 答案完整性 | `answer_completeness_score` | 是否覆盖题目要求的关键点、比较项或步骤 |
| 引用准确性 | `citation_accuracy_score` | 引用的文档 / chunk 是否能支撑关键结论 |
| 证据忠实性 | `faithfulness_score` | 答案是否被检索证据支持，是否存在无证据推断 |
| 综合辅助分 | `llm_judge_weighted_score` | 四个维度的简单平均，仅用于排序和排查，不作为主结论 |

失败类型字段：

```text
none
wrong_answer
incomplete_answer
weak_citation
unsupported_claim
over_refusal
off_topic
format_error
```

## 4. 评分标准

### 4.1 Answer Correctness

- `1`：核心结论正确，满足 `judge_rule`。
- `0.5`：方向基本正确，但遗漏关键限制、关键比较或部分事实。
- `0`：答偏、答错、与参考答案冲突，或该答时错误拒答。

### 4.2 Answer Completeness

- `1`：覆盖题目要求的主要要点。
- `0.5`：覆盖部分要点，但缺少必要比较、步骤或边界说明。
- `0`：只给空泛结论，未完成题目要求。

### 4.3 Citation Accuracy

- `1`：引用 chunk 能直接支撑答案关键结论。
- `0.5`：引用文档相关，但 chunk 支撑不够精确，或只支撑部分结论。
- `0`：无引用、引用错误、引用与答案无关，或引用不能支撑核心结论。

### 4.4 Faithfulness

- `1`：答案中的关键事实都能从检索证据中找到支持。
- `0.5`：大部分内容有证据，但存在轻微外推或证据不足。
- `0`：明显幻觉、无证据推断、把不确定内容写成确定结论。

## 5. 推荐使用命令

旧版答案正确率评分：

```powershell
uv run python run_score_answer_accuracy.py --results runs/results/c2_stage2_c1_hybrid_rerank_results.csv
```

新版多维评分：

```powershell
uv run python run_score_rag_multidim.py --results runs/results/c2_stage2_c1_hybrid_rerank_results.csv
```

多维评分脚本默认会读取 `data/processed/chunks.jsonl`，根据结果表中的 `top_chunk_ids`、`retrieved_chunk_ids`、`expanded_chunk_ids` 和 `final_citation_chunk_ids` 还原证据文本，再交给 LLM Judge。不要只把 chunk id 当作证据文本，否则 `Citation Accuracy` 和 `Faithfulness` 的判断会不可靠。

C3 候选题多维评分时，需要指定 C3 题库：

```powershell
uv run python run_score_rag_multidim.py `
  --results runs/results/c3_smoke_answers_for_judge.csv `
  --questions data/testset/questions_c3_candidates.csv `
  --references data/testset/references_c3_candidates.csv
```

## 6. 实验记录规范

AI Judge 结果可以进入实验记录，但必须注明：

1. 这是 `LLM-as-judge` 自动化辅助评分，不是最终人工分。
2. 使用了哪个 Prompt、哪个模型、哪个测试集和哪个结果文件。
3. 是否已由人工抽查或复核。
4. 若 AI Judge 与人工评分冲突，以人工评分为最终依据。

正式报告中建议写法：

```text
本实验同时引入 LLM-as-judge 辅助评分，用于批量检查答案正确性、完整性、引用准确性与证据忠实性。该评分结果用于辅助发现问题和进行阶段对比，最终结论仍结合人工复核结果给出。
```
