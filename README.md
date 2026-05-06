# Topic4 Agentic RAG Evaluation

本项目对应 110 实验室课题四，研究面向学习与知识服务任务的 Agentic RAG 技术增强与评测。

项目当前不是做一个完整的学习助手产品，而是搭建一个可复现实验工程：用同一知识库、同一测试集，对比 C0-C4 不同 RAG / Agentic RAG 配置，观察 query rewrite、混合检索、rerank、多轮检索、self-check 和工具调用等模块是否真的提升效果，以及带来多少延迟和 token 成本。

## 当前进度

截至当前版本，项目已经完成：

- 项目目录、`uv` 环境、Git 协作规范和 docs 文档入口。
- 从 `Agentic-RAG-110` 迁移并整理 C0 单文档本地 RAG baseline。
- 实现 C1 Query Rewrite 初版流程。
- 建立初版知识库登记表：`data/processed/documents.csv`，当前共 23 条文档记录。
- 准备首批 20 条测试题：`data/testset/questions.csv` 和 `data/testset/references.csv`。
- 生成初版 chunk 文件：`data/processed/chunks.jsonl`，当前共 475 个 chunk。
- 新增 C0/C1 批量实验脚本：`run_batch_experiments.py`。
- 完成一次 C0/C1 20 题批量实验。
- 新增 C0-C4 配置草稿、query rewrite prompt、self-check prompt。
- 接入 rerank 和 context neighbor 扩展的基础代码，后续作为 C2 实验的一部分继续验证。
- 当前 `ruff` 和 `pytest` 检查通过。

## 当前实验结果

最近一次 C0/C1 批量实验使用同一知识库和同一 20 条测试题。

本次实验边界：

- C0：普通 RAG，向量检索 + Top-K 证据 + 答案生成。
- C1：只在 C0 基础上新增 query rewrite。
- 本轮没有开启 BM25、hybrid retrieval、rerank、多轮检索、self-check 和工具调用。

结果摘要：

| 配置 | 题数 | 错误数 | 预期文档命中 | 平均延迟 | 平均 token |
| --- | ---: | ---: | ---: | ---: | ---: |
| C0 Naive RAG | 20 | 0 | 17/20 | 7441 ms | 915 |
| C1 Query Rewrite RAG | 20 | 0 | 18/20 | 11073 ms | 1328 |

注意：这里的“预期文档命中”只是文档级粗评估。`references.csv` 中的 `evidence_chunk_id` 还需要补齐，因此目前不能直接得出严格的 Recall@K、Citation Accuracy 或最终结论。

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
- `docs/interface_and_logging_rules.md`：C0/C1 输入输出结构和日志字段。
- `docs/batch_experiment_guide.md`：C0/C1 批量实验怎么跑、怎么看结果。
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

批量实验输入：

```text
data/processed/documents.csv
data/testset/questions.csv
data/testset/references.csv
```

批量实验输出：

```text
runs/logs/c0_naive/run_logs.jsonl
runs/results/c0_results.csv
runs/logs/c1_rewrite/run_logs.jsonl
runs/results/c1_results.csv
data/processed/chunks.jsonl
```

其中 `runs/logs/*` 和 `runs/results/*` 是本地实验输出，默认不提交到 GitHub。

## C0-C4 配置定位

| 配置 | 名称 | 当前定位 |
| --- | --- | --- |
| C0 | Naive RAG | 普通 RAG baseline：文档解析、切块、embedding、Top-K 检索、答案生成。 |
| C1 | Query Rewrite RAG | 在 C0 基础上新增查询诊断和 query rewrite。 |
| C2 | Advanced RAG | 后续重点验证 BM25、hybrid retrieval、rerank、context neighbor。 |
| C3 | Agentic Retrieval RAG | 后续新增任务规划、多轮检索和 self-check，不包含外部工具。 |
| C4 | Tool-Augmented Agentic RAG | 后续新增文件读取、代码执行、计算器、表格分析工具。 |

实验原则：每次只新增一类关键能力，避免变量混在一起导致结果无法解释。

## 下一步工作

当前最重要的不是继续堆功能，而是把 C0/C1 的评测做扎实。

优先级从高到低：

1. 补齐 `references.csv` 中的 `evidence_chunk_id`，至少先完成 20 条题的 gold chunk 标注。
2. 人工检查 `runs/results/c0_results.csv` 和 `runs/results/c1_results.csv`，标注 Answer Correctness 和 Citation Accuracy。
3. 整理 Q005、Q007、Q013 等典型案例，说明 C1 什么时候有效、什么时候收益有限。
4. 新增 `docs/evaluation_plan.md`，固定 Recall@5、Answer Correctness、Citation Accuracy、Latency、Token Usage 等指标的判定规则。
5. 在 C0/C1 结果稳定后，再进入 C2：BM25、hybrid retrieval、rerank 和 context neighbor 对比实验。
6. C2 仍然必须使用同一知识库、同一测试集，不能换题后再比较。

建议分工：

- 赵启行：统筹进度、检查 PR、维护 README / 实验记录 / 评测规则，负责 C1 结果分析。
- 唐宁：补 gold chunk、人工评分、整理失败案例和数据说明。
- 李金航：巩固 C0 接口，准备 C2 的 BM25、hybrid retrieval、rerank 实现与对齐。

## 协作注意事项

- GitHub 仓库是唯一同步来源，不用微信传代码。
- 每天开始工作前先 `git fetch` / `git pull`，确认自己基于最新远端。
- 不要随意强推 `main`，不要用无关历史覆盖 `main`。
- 新增依赖使用 `uv add`，不要各自随便 `pip install`。
- 不提交 `.env`、`.venv/`、API Key、临时日志和大体积索引。
- Demo 能跑不等于实验完成，必须有日志、指标、失败案例和成本分析。
