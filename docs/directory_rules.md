# 目录使用规范

本文档说明项目目录应该如何使用。所有成员必须按统一目录放文件，避免后期出现数据、代码、日志和报告混在一起的问题。

---

## 一、一级目录说明

| 目录 | 用途 | 是否提交 |
| :--- | :--- | :--- |
| `data/` | 原始资料、处理后数据、测试集 | 部分提交 |
| `src/` | 项目代码 | 提交 |
| `configs/` | C0-C4、消融和 C5 配置 | 提交 |
| `prompts/` | Prompt 模板 | 提交 |
| `runs/` | 实验日志、结果表、图表 | 重要结果可提交，临时结果不提交 |
| `docs/` | 项目文档、实验记录、失败案例、答辩材料 | 提交 |
| `.venv/` | 本地虚拟环境 | 不提交 |

---

## 二、data 目录

### 1. `data/raw/`

放原始资料，不随便改。

可以放：

- 学习资料。
- 实验室资料。
- 技术文档。
- CSV 表格。
- 代码片段。
- Benchmark 参考样例原始文件。

规则：

1. 原始文件尽量保持原样。
2. 不要在原始文件上直接修改。
3. 文件名要能看懂，避免 `新建文档1.pdf`。
4. 大体积无关文件不要放进项目。

建议后续细分：

```text
data/raw/learning_docs/
data/raw/lab_docs/
data/raw/tech_docs/
data/raw/tables_csv/
data/raw/code_snippets/
data/raw/benchmark_subset/
data/raw/web_snapshot_optional/
```

### 2. `data/processed/`

放处理后的数据。

包括：

| 文件或目录 | 用途 |
| :--- | :--- |
| `documents.csv` | 文档清单，记录 doc_id、标题、路径、类型 |
| `chunks.jsonl` | 文档切分后的 chunk |
| `bm25_index.pkl` | BM25 索引，可重新生成 |
| `vector_index/` | 向量索引，可重新生成 |

规则：

1. `documents.csv` 和 `chunks.jsonl` 可以提交，因为它们是实验输入的一部分。
2. 索引文件通常可以重新生成，体积大时不提交。
3. 正式实验前要记录处理脚本和参数。

### 3. `data/testset/`

放测试题和参考答案，正式实验前冻结。

包括：

| 文件 | 用途 |
| :--- | :--- |
| `questions.csv` | 自建测试题 |
| `references.csv` | 参考答案、证据和评分规则 |
| `benchmark_questions.csv` | 公共 Benchmark 参考子集问题 |
| `benchmark_references.csv` | Benchmark 参考答案和证据 |
| `c5_reference_questions.csv` | Dify/RAGFlow 横向参考任务 |

规则：

1. 每道题必须有 `question_id`。
2. 每道题必须能判断对错。
3. 每道题要标注任务类型和所需工具。
4. 正式实验前冻结，不能为了结果好看随便改。

---

## 三、src 目录

`src/` 放项目代码。

建议模块：

| 文件 | 作用 |
| :--- | :--- |
| `ingest.py` | 文档解析、清洗、切 chunk |
| `retrieval.py` | 向量检索、BM25、混合检索 |
| `rewrite.py` | query rewrite |
| `rerank.py` | 证据重排 |
| `tools.py` | 文件读取、代码执行、计算器、表格分析 |
| `agent.py` | C3/C4 Agentic RAG 流程 |
| `prompts.py` | 读取和管理 Prompt |
| `evaluate.py` | 计算指标 |
| `run_experiment.py` | 批量跑 C0-C4 |
| `demo.py` | Gradio Demo |
| `utils.py` | 通用工具函数 |

规则：

1. 不要把 API Key 写进代码。
2. 不要写死个人电脑路径。
3. 尽量让脚本从项目根目录运行。
4. 每个重要函数要有清晰输入和输出。

---

## 四、configs 目录

`configs/` 放实验配置。

建议文件：

```text
c0_naive.yaml
c1_rewrite.yaml
c2_advanced.yaml
c3_agentic_retrieval.yaml
c4_tool_augmented.yaml
c4_no_rewrite.yaml
c4_no_self_check.yaml
c4_no_tool.yaml
c5_open_source_reference.yaml
c4_adaptive_optional.yaml
```

规则：

1. 每个配置只控制一类实验能力。
2. 不要在代码里临时改参数后忘记记录。
3. 正式实验时配置文件要冻结。

---

## 五、prompts 目录

`prompts/` 放 Prompt，不要全部写死在代码里。

建议文件：

```text
query_rewrite_prompt.md
task_planner_prompt.md
answer_generation_prompt.md
self_check_prompt.md
tool_selection_prompt.md
judge_prompt.md
```

规则：

1. Prompt 修改会影响实验结果，所以正式实验前必须冻结。
2. 每次大改 Prompt 要在实验记录中说明。
3. 不同配置如果使用不同 Prompt，要明确记录。

---

## 六、runs 目录

`runs/` 放实验输出。

### 1. `runs/logs/`

放每次运行的 JSONL 日志。

日志应该记录：

- 原问题。
- 改写问题。
- 检索结果。
- rerank 结果。
- 工具调用。
- 工具输出。
- 最终答案。
- 引用。
- self-check。
- 延迟和 Token。
- 错误信息。

### 2. `runs/results/`

放统计后的结果表。

建议文件：

```text
main_results.csv
ablation_results.csv
benchmark_results.csv
c5_reference_results.csv
error_cases.csv
```

### 3. `runs/figures/`

放图表。

建议图表：

```text
retrieval_quality.png
answer_quality.png
tool_success.png
latency_cost.png
```

规则：

1. 临时日志和临时图表不提交。
2. 正式结果可以提交，但要说明来源。
3. 结果文件不要覆盖，建议带日期或 run_id。

---

## 七、docs 目录

`docs/` 放项目文档。

建议文件：

| 文件 | 用途 |
| :--- | :--- |
| `README.md` | docs 入口 |
| `environment_and_git_rules.md` | 环境和 Git 规范 |
| `directory_rules.md` | 目录使用规范 |
| `collaboration_workflow.md` | 三人分工与协作流程 |
| `c0_baseline_architecture.md` | C0 本地 RAG baseline 架构说明 |
| `experiment_notes.md` | 实验记录 |
| `data_description.md` | 数据说明 |
| `evaluation_plan.md` | 评测计划 |
| `failure_cases.md` | 失败案例 |
| `demo_script.md` | Demo 脚本 |
| `final_report_outline.md` | 结题报告提纲 |
| `slides_outline.md` | PPT 提纲 |

规则：

1. 文档不是最后才写，要边做边写。
2. 实验结论必须能追溯到结果表和日志。
3. 失败案例必须记录，不能只保留成功案例。

---

## 八、命名规范

### 1. 文件名

推荐使用小写英文、下划线或短横线：

```text
questions.csv
main_results.csv
c4_tool_augmented.yaml
query_rewrite_prompt.md
```

不推荐：

```text
最终版1.csv
新建文档.md
结果！！！！.csv
```

### 2. 编号

建议：

```text
doc_001
chunk_000001
Q001
RUN_20260505_C0
```

### 3. 结果文件

正式实验结果建议带日期或 run_id：

```text
main_results_20260520.csv
ablation_results_20260522.csv
```

---

## 九、冻结规范

正式实验前必须冻结：

| 内容 | 文件或目录 |
| :--- | :--- |
| 知识库 | `data/raw/`、`data/processed/documents.csv`、`chunks.jsonl` |
| 测试集 | `data/testset/questions.csv`、`references.csv` |
| Prompt | `prompts/` |
| 配置 | `configs/` |
| 代码 | Git commit 或 tag |
| 模型 | `.env` 中模型名，或实验记录 |
| 冻结快照存档（可选） | `frozen_experiment_versions/c0/`～`c4/`，按日期或 Git tag 再分子文件夹存放配置副本、manifest、结果摘要 |

冻结后可以修 bug，但不能为了提高结果随便改题、删题、改参考答案。
