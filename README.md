# Topic4 Agentic RAG Evaluation

本项目对应 110 实验室课题四，研究面向学习与知识服务任务的 Agentic RAG 技术增强与评测。

项目当前不是做完整学习助手产品，而是搭建一个可复现实验工程：在同一知识库、同一测试集上，对比 C0-C4 不同 RAG / Agentic RAG 配置，分析 query rewrite、hybrid retrieval、rerank、context expansion、self-check 和工具调用等模块是否真正提升效果，以及带来多少延迟和 token 成本。

## 当前阶段

截至 2026-05-13，项目处于：

```text
C2 正式复现实验完成 + C2 日志写入修复完成 + C2 人工评测待补齐阶段
```

当前重点：

1. C0/C1 已阶段性冻结，作为固定对照组。
2. C2 已完成正式复现实验，三阶段均 20 题、0 error。
3. C2 专属日志写入问题已修复，`runs/logs/c2_*` 现在能正确记录逐题 JSONL。
4. 下一步不是继续加功能，而是补齐 `manual_eval_c2.csv`，人工评估答案正确性和引用准确性。

基础检查：

```text
ruff: All checks passed
pytest: 24 passed
```

## 当前进度

已完成：

- C0 Naive RAG：普通 RAG baseline，已完成 20 题批量实验。
- C1 Query Rewrite RAG：已完成一次优化，已完成同一批 20 题实验。
- C2 Advanced RAG：已完成正式三阶段复现实验，包括 hybrid retrieval、rerank、context expansion。
- C2 日志修复：每个 C2 阶段现在会写入自己的 `runs/logs/<stage>/run_logs.jsonl`。
- AI Judge 辅助评测模块已接通，但只作为辅助，不能替代人工评分。
- 当前知识库包含 23 条文档记录、475 个 chunk、20 条核心测试题。
- `references.csv` 的 20 条 `evidence_chunk_id` 已补齐，pending 数为 0。
- `manual_eval_c0_c1.csv` 已建立，包含 40 行人工评分初稿。

尚未完成：

- C2 还缺人工 `Answer Correctness` 和 `Citation Accuracy`。
- 当前 20 条测试题只适合作为核心回归集，最终仍需扩展到 45-50 条。
- C3 的任务规划、多轮检索、self-check 还未正式验收。
- C4 的文件读取、代码执行、计算器、表格分析工具还未正式进入主线实验。
- 公共 Benchmark 参考子集和 Dify / RAGFlow 横向参考尚未开始。

## 实验结果摘要

当前实验均基于同一知识库和同一批 20 条核心测试题。

### C0/C1 文档级命中

| 配置 | 题数 | 错误数 | 文档级命中 | 未命中题目 | 平均延迟 | 平均 token |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| C0 Naive RAG | 20 | 0 | 17/20 | Q005、Q007、Q013 | 7382 ms | 962 |
| C1 Query Rewrite RAG | 20 | 0 | 19/20 | Q013 | 37060 ms | 1905 |

### C0/C1 人工评分初稿

| 配置 | Answer Correctness | Citation Accuracy |
| --- | ---: | ---: |
| C0 Naive RAG | 0.525 | 0.650 |
| C1 Query Rewrite RAG | 0.400 | 0.550 |

当前人工评分仍是草稿，但已经显示一个重要现象：C1 虽然提升了文档级命中率，但没有稳定转化为更高的答案正确性和引用准确性。

### C2 正式复现实验

固定参数：

```powershell
uv run python run_c2_retrieval_ablation.py --phase all --limit 20 --neighbors 1
```

| 配置 | 题数 | 错误数 | 文档级命中 | Gold chunk 命中 | 平均延迟 | 平均 token |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| C2 Stage1：C1 + hybrid retrieval | 20 | 0 | 19/20 | 9/20 | 17719 ms | 2143 |
| C2 Stage2：C1 + hybrid retrieval + rerank | 20 | 0 | 20/20 | 15/20 | 28761 ms | 12462 |
| C2 Stage3：C1 + hybrid retrieval + rerank + context expansion | 20 | 0 | 20/20 | 15/20 | 27887 ms | 14462 |

C2 日志校验：

| 阶段 | CSV 行数 | 日志行数 | 日志位置 |
| --- | ---: | ---: | --- |
| Stage1 | 20 | 20 | `runs/logs/c2_stage1_c1_hybrid/run_logs.jsonl` |
| Stage2 | 20 | 20 | `runs/logs/c2_stage2_c1_hybrid_rerank/run_logs.jsonl` |
| Stage3 | 20 | 20 | `runs/logs/c2_stage3_c1_hybrid_rerank_context/run_logs.jsonl` |

注意：文档级命中和 Gold chunk 命中只说明检索侧表现，不等于答案一定正确，也不等于引用一定可靠。C2 仍需唐宁补人工评分。

## 阶段性结论

1. C1 提高了文档级命中，但不是稳定更强。当前人工评分初稿中，C1 的答案正确性和引用准确性低于 C0。
2. Query rewrite 对模糊、口语化、非规范查询有帮助，但存在改写漂移风险，并显著增加延迟和 token 成本。
3. C2 的 hybrid retrieval 对文档召回有帮助，但 Stage1 的 Gold chunk 命中仍较低。
4. C2 的 rerank 明显改善检索侧排序，Stage2 的 Gold chunk 命中从 9/20 提升到 15/20。
5. C2 的 context expansion 没有进一步提升 Gold chunk 命中，且 token 成本更高；是否提升答案质量必须通过人工评分判断。
6. 当前研究重点应从“模块能跑”转向“模块是否有效、何时有效、成本是否可接受”。

## 项目目录

```text
data/       知识库材料、处理后数据、测试集
src/        项目代码
configs/    C0-C4 和消融实验配置
prompts/    Prompt 模板
runs/       实验日志、结果表、图表，本地生成，默认不提交
docs/       协作规范、接口规范、实验记录和实施说明
tests/      基础测试
archive/    本地实验备份，不提交
```

重点文档：

- `docs/README.md`：docs 目录导航。
- `docs/interface_and_logging_rules.md`：C0/C1/C2 输入输出结构和日志字段。
- `docs/batch_experiment_guide.md`：C0/C1 批量实验说明。
- `docs/c2_ablation_guide.md`：C2 三阶段消融实验说明。
- `docs/evaluation_plan.md`：人工评测流程和评分规则。
- `docs/failure_cases.md`：典型失败案例。
- `docs/manual_eval_c0_c1_summary.md`：C0/C1 人工评测摘要。
- `docs/evaluation_ai_judge.md`：AI Judge 模块说明。
- `docs/experiment_notes.md`：实验记录。

## 环境准备

项目统一使用 Python 3.12 和 `uv`。

```powershell
uv sync
uv run python --version
```

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

本地 `.env` 至少需要配置：

```text
ARK_API_KEY=your_key_here
DEEPSEEK_API_KEY=your_key_here
```

注意：

- `.env` 不能提交到 GitHub。
- 不要把 API Key 写进 Markdown、CSV、日志截图或聊天记录。
- 所有脚本尽量使用 `uv run python ...` 运行。

## 常用命令

基础检查：

```powershell
uv run ruff check .
uv run pytest
```

运行 C0/C1 批量实验：

```powershell
uv run python run_batch_experiments.py
```

运行 C2 小样本验证：

```powershell
uv run python run_c2_retrieval_ablation.py --phase 1 --limit 5
uv run python run_c2_retrieval_ablation.py --phase 2 --limit 5
uv run python run_c2_retrieval_ablation.py --phase 3 --limit 5 --neighbors 1
```

运行 C2 完整三阶段实验：

```powershell
uv run python run_c2_retrieval_ablation.py --phase all --limit 20 --neighbors 1
```

## 实验输出

C0/C1 批量实验输出：

```text
runs/logs/c0_naive/run_logs.jsonl
runs/results/c0_results.csv
runs/logs/c1_rewrite/run_logs.jsonl
runs/results/c1_results.csv
```

C2 三阶段实验输出：

```text
runs/logs/c2_stage1_c1_hybrid/run_logs.jsonl
runs/logs/c2_stage2_c1_hybrid_rerank/run_logs.jsonl
runs/logs/c2_stage3_c1_hybrid_rerank_context/run_logs.jsonl
runs/results/c2_stage1_c1_hybrid_results.csv
runs/results/c2_stage2_c1_hybrid_rerank_results.csv
runs/results/c2_stage3_c1_hybrid_rerank_context_results.csv
runs/results/c2_ablation_summary.json
runs/results/c2_ablation_report.md
```

其中 `runs/logs/*` 和 `runs/results/*` 是本地实验输出，默认不提交到 GitHub。

## C0-C4 配置定位

| 配置 | 名称 | 当前定位 |
| --- | --- | --- |
| C0 | Naive RAG | 普通 RAG baseline：文档解析、切块、embedding、Top-K 检索、答案生成。 |
| C1 | Query Rewrite RAG | 在 C0 基础上新增 query rewrite，包括查询诊断、检索式改写、多候选 query 和保守改写判断。 |
| C2 | Advanced RAG | 在 C1 基础上验证 hybrid retrieval、rerank、context expansion。 |
| C3 | Agentic Retrieval RAG | 后续新增任务规划、多轮检索和 self-check，不包含外部工具。 |
| C4 | Tool-Augmented Agentic RAG | 后续新增文件读取、代码执行、计算器、表格分析工具。 |

实验原则：每次只新增一类关键能力，避免变量混在一起导致结果无法解释。

## 下一步工作

优先级从高到低：

1. 唐宁建立 `data/testset/manual_eval_c2.csv`，对 C2 Stage1/Stage2/Stage3 分别评分 Answer Correctness 和 Citation Accuracy。
2. 先完成 Stage2 的 20 题人工评分，再补 Q005、Q007、Q013、Q018 的三阶段横向案例分析。
3. 赵启行汇总 C0/C1/C2 总表：文档命中、Gold chunk 命中、答案正确性、引用准确性、延迟、token。
4. 李金航解释 C2 三阶段收益与成本，尤其是 rerank 提升和 context expansion 的边界。
5. C2 人工验收后，再决定是否阶段性冻结 C2。
6. C2 冻结后，再进入 C3：任务规划、多轮检索和 self-check。
7. C3 稳定后，再进入 C4：文件读取、代码执行、计算器和表格分析工具调用。

建议分工：

- 赵启行：统筹阶段冻结、检查结论表述、推进 C2 验收和最终报告逻辑。
- 唐宁：复核 C0/C1 人工评分，补充 C2 人工评分，维护失败案例。
- 李金航：解释 C2 三阶段收益与成本，维护 hybrid retrieval、rerank、context expansion 相关代码。

## 协作注意事项

- GitHub 仓库是唯一同步来源。
- 每天开始工作前先 `git fetch` / `git pull`，确认自己基于最新远端。
- 不要随意强推 `main`，不要用无关历史覆盖 `main`。
- 新增依赖使用 `uv add`，不要各自随便 `pip install`。
- 不提交 `.env`、`.venv/`、API Key、临时日志、大体积索引和本地 `archive/` 备份。
- Demo 能跑不等于实验完成，必须有日志、指标、失败案例和成本分析。
