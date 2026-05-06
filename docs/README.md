# docs 目录说明

本目录用于保存项目协作规范、工程接口、实验记录、数据说明、评测计划和后续答辩材料。所有成员在写代码、整理数据、跑实验之前，都应先阅读这里的规范文档。

当前原则是：重要规则写进文档，不只在群聊里口头说明；实验结论必须能追溯到数据、日志、结果表或失败案例。

## 1. README 文件如何区分

项目里会出现多个 README，它们的作用不同：

| 文件位置 | 作用 |
| --- | --- |
| `README.md` | 项目总入口，说明项目定位、运行方式和当前代码状态。 |
| `docs/README.md` | 文档目录导航，说明 docs 里每个文档负责什么。 |
| `data/*/README.md` | 数据目录说明，只解释该数据目录应该放什么、不应该放什么。 |
| `runs/*/README.md` | 实验输出目录说明，只解释日志、结果表、图表如何保存。 |
| `prompts/README.md` | Prompt 目录说明，说明 Prompt 如何命名、冻结和记录版本。 |

不要把所有内容都写进一个 README。项目总说明放根目录 README，协作和实验规范放 docs，数据说明放 data，实验输出说明放 runs。

### 技术说明（可选查阅）

| 文档 | 作用 |
| :--- | :--- |
| `chroma_integration_and_langchain_reference.md` | Chroma 在本项目中的真实接入方式；与 LangChain 的关系及报告撰写注意事项 |

## 2. 当前必读文档

| 文档 | 当前状态 | 作用 |
| --- | --- | --- |
| `environment_and_git_rules.md` | 已建立 | 说明 Python 版本、uv 使用、`.env`、`.env.example`、Git 分支、commit 和 PR 规范。 |
| `directory_rules.md` | 已建立 | 说明项目目录如何使用，哪些文件可以提交，哪些文件不能提交。 |
| `collaboration_workflow.md` | 已建立 | 统一说明三人分工、近期交付物、每日同步、每周验收、阶段验收和冲突处理。 |
| `c0_baseline_architecture.md` | 已建立 | 说明迁移来的 C0 单文档本地 RAG baseline 的代码结构、数据流和模块边界。 |
| `experiment_notes.md` | 已建立 | 记录每天实验过程、运行命令、结果文件、问题和解决办法。 |
| `interface_and_logging_rules.md` | 已建立 | 固定 C0-C1 的输入输出结构、日志字段、C1 验收标准和测试办法。 |
| `batch_experiment_guide.md` | 已建立 | 说明如何运行 C0/C1 批量实验、检查输出文件、解释初版结果和处理常见问题。 |
| `c2_ablation_guide.md` | 已建立 | C2 检索消融（混合 / +重排 / +邻接上下文）脚本用法与输出说明。 |
| `evaluation_ai_judge.md` | 已建立 | 独立 AI 评判（LLM-as-judge）模块定位、字段与与人评对齐说明。 |

说明：原 `team_roles.md` 的成员分工内容已经合并进 `collaboration_workflow.md`，后续不再单独维护 `team_roles.md`。

其中，`interface_and_logging_rules.md` 是当前 C1、C2 对齐接口时最重要的文档。即使 C0 后续继续整理，也应尽量保持其中约定的数据结构稳定。

## 3. 当前工程进展记录

截至当前阶段，项目已经完成：

- 项目目录、uv 环境和基础协作规范已经建立。
- 迁移进来的代码已定位为 C0 Naive RAG / 单文档本地 RAG baseline，不是完整 Agentic RAG。
- C0 已具备单文档解析、切块、embedding、内存向量 Top-K 检索和答案生成的基础链路。
- C1 已开始实现 query rewrite，并新增了结构化接口、日志字段和基础测试。
- 已建立一个最小样例文档：`data/raw/learning_docs/python_basic_sample.md`，用于验证单文档解析、切块和后续 C0/C1 小样例运行。
- 已建立初版知识库登记表：`data/processed/documents.csv`，当前包含 23 条文档记录。
- 已准备首批 20 条测试题：`data/testset/questions.csv` 和 `data/testset/references.csv`。
- 已新增 C0/C1 批量实验入口：`run_batch_experiments.py`。
- 已完成一次 C0/C1 20 题批量实验，生成 `runs/logs/c0_naive/run_logs.jsonl`、`runs/results/c0_results.csv`、`runs/logs/c1_rewrite/run_logs.jsonl` 和 `runs/results/c1_results.csv`。

当前尚未完成：

- 持久化向量数据库尚未建立，当前批量实验仍以 `SimpleVectorIndex` 内存索引为主。
- `references.csv` 中的 `evidence_chunk_id` 尚未补齐，正式 chunk 级指标还不能计算。
- C0/C1 的人工答案质量评分、引用可信度评分和失败案例分析尚未完成。
- C2 检索链路（BM25、混合检索、rerank、邻接上下文）已在代码中实现；**2026-05-06** 由李金航完成首轮 **C2 三阶段消融**跑通，记录见 `experiment_notes.md` 同日期条目，结果见 `runs/results/c2_*`。
- C3 的任务规划、多轮检索和 self-check 尚未实现。
- C4 的文件读取、代码执行、计算器、表格分析工具尚未实现。
- 正式测试集、公共 Benchmark 参考子集和 Dify/RAGFlow 横向对比尚未开始。

## 4. 后续需要补充的文档

这些文档可以等对应阶段开始后再建立，不需要现在一次性写完。

| 文档 | 建议建立时间 | 作用 |
| --- | --- | --- |
| `project_plan.md` | C1 稳定后 | 细化 C0-C4 实验主线、阶段计划、每阶段验收标准。 |
| `data_description.md` | 正式收集资料时 | 记录知识库材料来源、文档编号、chunk 编号规则、测试集字段和数据冻结版本。 |
| `evaluation_plan.md` | C0/C1 首轮批量结果复核时 | 定义 Recall@5、MRR@10、Answer Correctness、Citation Accuracy、Tool Call Success、Latency 等指标。 |
| `failure_cases.md` | 第一次批量实验后 | 记录失败案例、错误归因和后续修正方向，至少整理 10 个典型失败案例。 |
| `demo_script.md` | Demo 前一周 | 记录现场演示问题、展示流程、备用问题和异常处理方案。 |
| `final_report_outline.md` | 结题报告前 | 整理最终报告结构、实验结果表、图表和结论。 |
| `slides_outline.md` | 答辩 PPT 前 | 整理答辩逻辑、每页 PPT 内容和成员讲解分工。 |

## 5. 当前阶段的重点文档任务

近期不需要继续堆文档，重点是让文档服务 C0-C1 实验。

当前优先级：

1. 维护 `interface_and_logging_rules.md`，确保 C0、C1、后续 C2 都按同一输入输出结构写代码。
2. 在 `experiment_notes.md` 记录每次运行命令、测试问题、日志路径和结果。
3. 等正式知识库开始整理后，再建立 `data_description.md`。
4. 当前已经跑完首轮 C0/C1 批量对比，下一步应补充 `evaluation_plan.md` 和失败案例记录。

## 6. 文档更新规范

- 文档更新应尽量写清楚“为什么改”“改了什么”“影响谁”。
- 与接口、日志、数据字段有关的修改，要优先通知所有成员。
- 测试集、Prompt、配置文件和实验结果一旦冻结，必须在文档中记录冻结日期、文件路径和版本。
- 不要把个人 API Key、`.env` 内容、临时日志、大体积索引文件写进文档或提交到仓库。
- 成员个人临时任务说明可以先本地保存，只有需要团队长期参考时再纳入 docs。

## 7. 组长检查清单

赵启行作为组长，每次阶段推进前建议检查：

- 三个人是否都能 `uv sync` 并正常运行项目。
- 当前任务是否有明确输入、输出和验收标准。
- C0、C1、C2 是否使用同一批知识库和同一批测试题。
- 新增代码是否按 `interface_and_logging_rules.md` 输出日志。
- 实验结果是否能从 `runs/logs/`、`runs/results/` 或 `docs/experiment_notes.md` 追溯。
- 是否有成员在没有同步 main 的情况下单独推进大量修改。

文档不是为了显得项目复杂，而是为了让三个人在 50 多天内少走弯路，能把实验、代码和报告稳定对齐。
