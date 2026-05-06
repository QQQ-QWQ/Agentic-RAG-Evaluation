# Topic4 Agentic RAG Evaluation

本项目对应 110 实验室课题四，研究面向学习与知识服务任务的 Agentic RAG 技术增强与评测。

项目当前不是做一个完整的学习助手产品，而是搭建一个可复现实验工程：用同一知识库、同一测试集，对比 C0-C4 不同 RAG / Agentic RAG 配置，观察 query rewrite、混合检索、rerank、多轮检索、self-check 和工具调用等模块是否真的提升效果，以及带来多少延迟和 token 成本。

## 当前版本

当前主线以远端 `origin/main` 为准：

```text
da41e53 feat: sync experiment pipeline, C2 ablation, and evaluation tooling
```

当前本地 `main` 已对齐 `origin/main`。基础检查通过：

```powershell
uv run ruff check .
uv run pytest
```

当前测试结果：

```text
ruff: All checks passed
pytest: 23 passed
```

## 当前进度

截至 2026-05-07，项目已经完成：

- 项目目录、`uv` 环境、Git 协作规范和 docs 文档入口。
- C0 Naive RAG：普通 RAG baseline，包含文档解析、切块、embedding、Top-K 检索和答案生成。
- C1 Query Rewrite RAG：在 C0 基础上新增查询诊断、检索式改写、多候选 query 和保守改写判断。
- C2 Advanced RAG：已接通混合检索、rerank、邻接上下文补全三阶段实验流程。
- AI Judge 辅助评测模块：已实现 LLM-as-judge 答案打分入口，后续用于和人工评分对照。
- 初版知识库登记表：`data/processed/documents.csv`，当前共 23 条文档记录。
- 初版 chunk 文件：`data/processed/chunks.jsonl`，当前共 475 个 chunk。
- 首批 20 条核心测试题：`data/testset/questions.csv` 和 `data/testset/references.csv`。
- C0/C1 批量实验脚本：`run_batch_experiments.py`。
- C2 三阶段消融脚本：`run_c2_retrieval_ablation.py`。
- C2 答案自动评分脚本：`run_c2_ablation_answer_accuracy.py`、`run_score_answer_accuracy.py`。
- C0/C1 冻结快照目录：`frozen_experiment_versions/`。

当前尚未完成：

- `references.csv` 中前 20 题的 `evidence_chunk_id` 仍需补齐。
- C0/C1 的人工 `Answer Correctness`、`Citation Accuracy` 评分尚未完成。
- C2 三阶段结果需要在组长电脑复现，并结合人工评分复核。
- C3 的任务规划、多轮检索、self-check 尚未正式进入主线。
- C4 的文件读取、代码执行、计算器、表格分析工具尚未正式进入主线。
- 正式测试集仍需从 20 条扩展到 45-50 条，并补充 10-15 条公共 Benchmark 参考样例。
- Dify / RAGFlow 横向参考对比尚未开始。

## 阶段性实验结果

### C0/C1 批量实验

最近一次 C0/C1 批量实验使用同一知识库和同一 20 条测试题。

实验边界：

- C0：普通 RAG，向量检索 + Top-K 证据 + 答案生成。
- C1：只在 C0 基础上新增 query rewrite。
- C1 不包含 BM25、hybrid retrieval、rerank、多轮检索、self-check 和工具调用。
- README 中统一称为 C1；实验记录中为了区分优化前后，会把优化后一版写作 `C1-final`。

结果摘要：

| 配置 | 题数 | 错误数 | 预期文档命中 | 未命中题目 | 平均延迟 | 平均 token |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| C0 Naive RAG | 20 | 0 | 17/20 | Q005、Q007、Q013 | 7382 ms | 962 |
| C1 Query Rewrite RAG | 20 | 0 | 19/20 | Q013 | 37060 ms | 1905 |

阶段性观察：

- C1 相比 C0 在文档级命中上有提升，主要改善了模糊、口语化、非规范表达问题。
- C1 的收益集中在 `fuzzy_query` 类型任务；对简单事实问答，提升不明显。
- C1 的代价明显更高，平均延迟和 token 使用量均高于 C0。
- Q013 仍然失败，说明单纯 query rewrite 不能解决所有问题；该问题更像是 chunk 排序、指定文件定位、hybrid retrieval 或 rerank 的问题，应交给 C2 分析。

注意：这里的“预期文档命中”只是文档级粗评估。`references.csv` 中的 `evidence_chunk_id` 还需要补齐，因此目前不能直接得出严格的 chunk 级 Recall、Citation Accuracy 或最终答案质量结论。

### C2 三阶段实验状态

C2 当前已经接通三阶段流程：

| 阶段 | 配置 | 作用 |
| --- | --- | --- |
| 阶段 1 | C1 + hybrid retrieval | 验证混合检索是否改善文档命中 |
| 阶段 2 | C1 + hybrid retrieval + rerank | 验证 rerank 是否改善证据排序和答案质量 |
| 阶段 3 | C1 + hybrid retrieval + rerank + context expansion | 验证邻接上下文补全是否改善答案生成 |

根据当前实验记录，C2 已有初步结果：

| 阶段 | 文档级命中 | 初步观察 |
| --- | ---: | --- |
| 阶段 1 | 20/20 | 混合检索对文档级命中有明显帮助 |
| 阶段 2 | 20/20 | rerank 可能改善答案质量，但 token 和延迟成本上升 |
| 阶段 3 | 19/20 | 上下文补全不一定稳定提升，可能引入噪声 |

说明：

- C2 结果需要继续复现和人工复核。
- 文档级命中高不等于答案一定正确。
- AI Judge 的打分只能作为辅助结果，最终结论必须经过人工评分确认。

## 当前结论

当前可以得到的阶段性结论：

1. C0/C1 已经可以作为阶段性冻结基线，后续除明显 bug 外，不再继续修改 C1。
2. Query rewrite 对模糊表达、口语化提问、语义不完整问题有效，但会显著增加延迟和 token 成本。
3. 仅靠 query rewrite 不能解决 chunk 干扰、指定文件定位和排序问题，因此需要 C2 的 hybrid retrieval 与 rerank。
4. C2 的混合检索和 rerank 已经具备进一步验证价值，但结论还不能只看文档命中率，必须结合人工答案评分和引用可信度。
5. 当前 20 条测试题适合作为核心回归测试集，但不适合作为最终研究结论的唯一依据，后续需要扩充。
6. AI Judge 模块可以提高批量评测效率，但不能代替人工评测；它更适合作为后续 self-check / 答案验证链路的参考模块。

## 项目目录

```text
data/       知识库材料、处理后数据、测试集
src/        项目代码
configs/    C0-C4 和消融实验配置
prompts/    Prompt 模板
runs/       实验日志、结果表、图表，本地生成，不提交正式日志
docs/       协作规范、接口规范、实验记录和实施说明
tests/      基础测试
```

重点文档：

- `docs/README.md`：docs 目录导航。
- `docs/environment_and_git_rules.md`：环境、uv、Git 分支和提交规范。
- `docs/collaboration_workflow.md`：三人分工、同步方式和协作流程。
- `docs/interface_and_logging_rules.md`：C0/C1/C2 输入输出结构和日志字段。
- `docs/batch_experiment_guide.md`：C0/C1 批量实验怎么跑、怎么看结果。
- `docs/c2_ablation_guide.md`：C2 三阶段消融实验怎么跑、怎么看结果。
- `docs/evaluation_ai_judge.md`：AI Judge 模块定位、输出字段和使用边界。
- `docs/experiment_notes.md`：实验记录。
- `docs/c0_baseline_architecture.md`：C0 baseline 架构说明。

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

运行基础检查：

```powershell
uv run ruff check .
uv run pytest
```

运行单文档 RAG：

```powershell
uv run python main.py rag "data/raw/learning_docs/python_basic_sample.md" "切片咋取中间几个元素？"
```

运行 C1 单文档 query rewrite demo：

```powershell
uv run python c1_rewrite_demo.py "data/raw/learning_docs/python_basic_sample.md" "切片咋取中间几个元素？"
```

运行 C0/C1 批量实验：

```powershell
uv run python run_batch_experiments.py
```

运行 C2 三阶段小样本验证：

```powershell
uv run python run_c2_retrieval_ablation.py --phase 1 --limit 5
uv run python run_c2_retrieval_ablation.py --phase 2 --limit 5
uv run python run_c2_retrieval_ablation.py --phase 3 --limit 5 --neighbors 1
```

运行 C2 完整三阶段实验：

```powershell
uv run python run_c2_retrieval_ablation.py --phase all
```

## 实验输出

C0/C1 批量实验输入：

```text
data/processed/documents.csv
data/testset/questions.csv
data/testset/references.csv
```

C0/C1 批量实验输出：

```text
runs/logs/c0_naive/run_logs.jsonl
runs/results/c0_results.csv
runs/logs/c1_rewrite/run_logs.jsonl
runs/results/c1_results.csv
data/processed/chunks.jsonl
```

C2 三阶段实验输出：

```text
runs/results/c2_stage1_c1_hybrid_results.csv
runs/results/c2_stage2_c1_hybrid_rerank_results.csv
runs/results/c2_stage3_c1_hybrid_rerank_context_results.csv
runs/results/c2_ablation_summary.json
runs/results/c2_ablation_report.md
runs/logs/c2_stage1_c1_hybrid/run_logs.jsonl
runs/logs/c2_stage2_c1_hybrid_rerank/run_logs.jsonl
runs/logs/c2_stage3_c1_hybrid_rerank_context/run_logs.jsonl
```

其中 `runs/logs/*` 和 `runs/results/*` 是本地实验输出，默认不提交到 GitHub。

## C0-C4 配置定位

| 配置 | 名称 | 当前定位 |
| --- | --- | --- |
| C0 | Naive RAG | 普通 RAG baseline：文档解析、切块、embedding、Top-K 检索、答案生成。 |
| C1 | Query Rewrite RAG | 在 C0 基础上新增 query rewrite，包含查询诊断、检索式改写、多候选 query 和保守改写判断。 |
| C2 | Advanced RAG | 在 C1 基础上验证 hybrid retrieval、rerank、context neighbor。 |
| C3 | Agentic Retrieval RAG | 后续新增任务规划、多轮检索和 self-check，不包含外部工具。 |
| C4 | Tool-Augmented Agentic RAG | 后续新增文件读取、代码执行、计算器、表格分析工具。 |

实验原则：每次只新增一类关键能力，避免变量混在一起导致结果无法解释。

## 下一步工作

当前最重要的不是继续堆功能，而是把 C0/C1/C2 的评测做扎实。

优先级从高到低：

1. 补齐 `references.csv` 中的 `evidence_chunk_id`，至少先完成前 20 条题的 gold chunk 标注。
2. 人工检查 `runs/results/c0_results.csv` 和 `runs/results/c1_results.csv`，标注 Answer Correctness 和 Citation Accuracy。
3. 在组长电脑复现 C2 三阶段实验，确认 C2 输出和李金航记录一致。
4. 对 C2 三阶段结果做人评复核，重点判断 rerank 和上下文补全是否真的改善答案质量。
5. 整理 Q005、Q007、Q013 等典型案例，说明 C1/C2 什么时候有效、什么时候收益有限。
6. 新增或补全 `docs/evaluation_plan.md`，固定 Recall@5、Answer Correctness、Citation Accuracy、Latency、Token Usage 等指标的判定规则。
7. 将测试集从 20 条扩展到 45-50 条，但扩充前先冻结当前 20 条核心回归集。
8. 加入 10-15 条公共 Benchmark 参考样例，作为权威参照，不替代自建测试集。
9. C2 验收稳定后，再进入 C3：任务规划、多轮检索和 self-check。
10. C3 稳定后再进入 C4：文件读取、代码执行、计算器和表格分析工具。

建议分工：

- 赵启行：统筹进度、检查 PR、维护 README / 实验记录 / 评测规则，负责 C1/C2 结果分析和阶段冻结。
- 唐宁：补 gold chunk、人工评分、整理失败案例和数据说明。
- 李金航：复现并解释 C2 三阶段实验，维护 hybrid retrieval、rerank、context expansion 相关代码。

## 协作注意事项

- GitHub 仓库是唯一同步来源，不用微信传代码。
- 每天开始工作前先 `git fetch` / `git pull`，确认自己基于最新远端。
- 不要随意强推 `main`，不要用无关历史覆盖 `main`。
- 新增依赖使用 `uv add`，不要各自随便 `pip install`。
- 不提交 `.env`、`.venv/`、API Key、临时日志和大体积索引。
- Demo 能跑不等于实验完成，必须有日志、指标、失败案例和成本分析。
