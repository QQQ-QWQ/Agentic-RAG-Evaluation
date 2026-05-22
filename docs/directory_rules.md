# 目录使用规范

本文档说明仓库目录职责、哪些内容应提交、哪些内容只保留在本地，以及正式实验前需要冻结的内容。当前根目录 `README.md` 只保留开题报告正文；运行方式和当前进度见根目录 `current progress.md`。

## 1. 一级目录与根文件

| 路径 | 作用 | 是否提交 |
| --- | --- | --- |
| `README.md` | 开题报告正文与参考文献 | 提交 |
| `current progress.md` | 当前进度、运行入口、下一步任务 | 提交 |
| `main.py` | 统一 CLI 入口 | 提交 |
| `run_batch_experiments.py` | C0/C1 批量实验入口 | 提交 |
| `run_c2_retrieval_ablation.py` | C2 三阶段消融入口 | 提交 |
| `run_c34_batch_eval.py` | C3/C4 批量评测入口 | 提交 |
| `run_score_rag_multidim.py` | 多维 AI Judge 辅助评分入口 | 提交 |
| `src/` | 项目核心代码 | 提交 |
| `configs/` | C0-C4、消融和可选 C5 配置 | 提交 |
| `prompts/` | Query rewrite、self-check、judge 等 Prompt | 提交，正式实验前冻结 |
| `data/` | 原始资料、处理数据、测试集 | 部分提交 |
| `docs/` | 规范、架构、实验记录、专题说明 | 提交 |
| `tests/` | 单元测试 | 提交 |
| `runs/` | 本地实验日志、结果表、图表 | 默认不提交 |
| `archive/` | 本地备份、历史输出 | 不提交 |
| `.env` | 本地密钥 | 不提交 |
| `.venv/` | uv 虚拟环境 | 不提交 |

## 2. 代码结构

核心代码位于 `src/agentic_rag/`：

| 目录 | 作用 |
| --- | --- |
| `documents/` | 文档解析、会话文档、传入文件检查 |
| `rag/` | 分块、内存向量索引、Chroma 持久化、上下文扩展 |
| `pipelines/` | C0-C2 RAG 编排 |
| `experiment/` | 批量实验、知识库同步、C3/C4 batch |
| `deep_planning/` | L1 规划、L2 Deep Agent、工具注册 |
| `orchestration/` | Agentic RAG 编排循环、L3 研判、重试/重规划 |
| `tools/` | C4 外部工具：文件、计算、表格、代码、网页、shell |
| `sandbox/` | 本地子进程沙箱与受限 shell |
| `telemetry/` | 会话审计、trace、chat transcript |
| `evaluation/` | 人工/AI Judge 辅助评分 |
| `cli/` | `main.py` 子命令、C3/C4 Gradio/console 客户端 |
| `runtime/` | `QueryEngine`、REPL、headless 运行骨架 |

新增功能时，优先放入对应包内，不要在根目录继续新增临时 demo 脚本。确实需要根入口时，应在 `main.py` 或现有 `run_*.py` 体系中接入。

## 3. data 目录

### 3.1 `data/raw/`

原始资料目录。详见 `data/raw/README.md`。

系统知识库扫描范围主要包括：

```text
data/raw/learning_docs/
data/raw/lab_docs/
data/raw/tech_docs/
data/raw/tables_csv/
data/raw/code_snippets/
```

不建议作为系统全库来源的目录：

```text
data/raw/session_upload/    # 会话临时上传
data/raw/user_docs/         # 历史用户文档
data/raw/web_snapshots/     # Firecrawl 快照，可选
```

规则：

1. 原始资料尽量保持原样。
2. 文件名必须可读，不使用 `新建文档1.pdf` 一类名称。
3. 与实验无关的大文件不放入仓库。
4. 写入 `data/raw/` 后，需运行 `uv run python main.py kb sync` 才能进入系统全库索引。

### 3.2 `data/processed/`

处理后数据，如 `documents.csv`、`chunks.jsonl`、索引缓存等。当前工程中这些文件多为可再生结果，默认不应作为人工编辑对象。

规则：

1. 优先通过 `main.py kb sync` 生成。
2. 不手工改 `documents.csv` 和 `chunks.jsonl` 来“修结果”。
3. 如果正式实验需要冻结 processed 数据，应在 `experiment_notes.md` 记录生成命令、Git commit 和参数。

### 3.3 `data/testset/`

测试集与参考答案目录。

| 文件 | 作用 |
| --- | --- |
| `questions.csv` | Q001-Q020 主测试题 |
| `references.csv` | 主测试题参考答案、gold doc/chunk |
| `questions_c3_candidates.csv` | Q021-Q030 C3 候选题 |
| `references_c3_candidates.csv` | C3 候选题参考证据 |
| `manual_eval_c0_c1.csv` | C0/C1 人工评分 |
| `manual_eval_c2.csv` | C2 人工评分 |

后续建议新增：

```text
manual_eval_c3_smoke.csv
manual_eval_c4_tools.csv
benchmark_questions.csv
benchmark_references.csv
c5_reference_questions.csv
```

规则：

1. 每道题必须有 `question_id`。
2. 每道题必须能判断对错。
3. 工具型题必须标注 `required_tool`。
4. 正式实验前冻结，不能为了结果好看改题或改参考答案。

## 4. configs 与 prompts

`configs/` 控制实验档位和消融；`prompts/` 存 Prompt。正式实验前必须冻结：

```text
configs/
prompts/
模型名称
测试集
知识库版本
Git commit 或 tag
```

Prompt 修改会影响结果。每次大改 Prompt 或配置，都要记录到 `docs/experiment_notes.md`。

## 5. runs 与 archive

`runs/` 是本地实验输出目录。默认不提交 GitHub。

常见输出：

```text
runs/logs/c0_naive/run_logs.jsonl
runs/results/c0_results.csv
runs/logs/c2_stage*_*/run_logs.jsonl
runs/results/c2_ablation_summary.json
runs/logs/c3_agentic_retrieval_batch/run_logs.jsonl
runs/logs/c4_tool_augmented_batch/run_logs.jsonl
runs/logs/audit/sessions/<id>/trace.jsonl
```

规则：

1. 临时日志和结果不提交。
2. 如果需要给组员或老师查看，单独打包或摘要写入 docs。
3. 正式图表和结论表应进入报告或 docs，而不是直接依赖本地 `runs/`。
4. `archive/` 只作本地备份，不提交。

## 6. docs 目录

`docs/` 按职责分组维护，入口见 `docs/README.md`。

| 类别 | 主文档 |
| --- | --- |
| 文档导航 | `docs/README.md` |
| 协作规范 | `environment_and_git_rules.md`、`collaboration_workflow.md`、`directory_rules.md` |
| 架构说明 | `ARCHITECTURE.md`、`agent_runtime_architecture.md`、`c0_baseline_architecture.md` |
| 实验指南 | `batch_experiment_guide.md`、`c2_ablation_guide.md`、`c3_smoke_experiment_guide.md` |
| 评测规范 | `evaluation_plan.md`、`evaluation_ai_judge.md` |
| 实验记录 | `experiment_notes.md` |
| 阶段总结 | `manual_eval_c0_c1_summary.md`、`c2_three_layer_retrieval_report.md`、`failure_cases.md` |

不要把同一个运行命令同时维护在多个文档里。当前运行入口以 `current progress.md` 为准。

## 7. 命名规范

推荐：

```text
questions.csv
main_results_20260520.csv
c4_tool_augmented.yaml
query_rewrite_prompt.md
manual_eval_c3_smoke.csv
```

不推荐：

```text
最终版1.csv
新建文档.md
结果！！！！.csv
```

编号建议：

```text
doc_001
chunk_000001
Q001
RUN_20260505_C0
```

## 8. 冻结规范

正式实验前必须冻结：

| 内容 | 文件或目录 |
| --- | --- |
| 知识库 | `data/raw/`、`data/processed/` 生成版本 |
| 测试集 | `data/testset/questions.csv`、`references.csv` 和扩充题 |
| Prompt | `prompts/` |
| 配置 | `configs/` |
| 代码 | Git commit 或 tag |
| 模型 | `.env` 中模型名或实验记录 |
| 评测规则 | `docs/evaluation_plan.md` |

冻结后可以修 bug，但不能为了提高结果随意改题、删题、改参考答案或换模型而不记录。
