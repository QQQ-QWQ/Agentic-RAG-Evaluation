# 实验记录

本文档用于记录每天的实验进展、运行命令、结果文件、问题和下一步安排。它不是流水账，而是后续写结题报告、失败分析和复现实验的重要依据。

记录原则：

1. 只要运行了重要脚本、修改了数据、Prompt、配置、模型或接口，都要记录。
2. 成功和失败都要记录，失败案例后续可能比成功案例更有价值。
3. 记录必须写清楚输入数据、运行命令、输出文件和主要结论。
4. 不要把 API Key、`.env` 内容、个人隐私路径或临时大文件写进记录。
5. 正式实验前，要记录测试集、Prompt、配置和模型的冻结版本。

## 记录模板

```text
日期：
记录人：
阶段：
对应任务：
运行命令：
输入数据：
输出文件：
主要结果：
遇到问题：
失败类型：
下一步：
```

## 实验运行记录模板

```text
run_id：
config：C0 / C1 / C2 / C3 / C4 / ablation / C5
测试集版本：
知识库版本：
Prompt 版本：
模型：
运行命令：
日志路径：
结果路径：
主要指标：
备注：
```

## 2026-05-05 项目初始化与工程规范建立

记录人：赵启行

阶段：阶段 0，项目启动与环境统一。

已完成：

- 建立项目基础目录：`data/`、`src/`、`configs/`、`prompts/`、`runs/`、`docs/`。
- 使用 uv 初始化项目环境。
- 固定 Python 版本，当前本地验证版本为 Python 3.12。
- 建立 `.env.example`、`.gitignore`、`pyproject.toml`、`uv.lock`。
- 建立基础协作文档和目录规范文档。

关键命令：

```powershell
uv sync
uv run python --version
```

当前结论：

- 项目环境已具备统一安装和运行基础。
- `.venv/` 由 uv 本地生成，不提交到 GitHub。
- `.env` 用于本地 API Key，不提交到 GitHub。

遗留问题：

- 目前正式知识库和测试集尚未建立。
- 组员需要 clone 仓库后运行 `uv sync` 验证环境。

## 2026-05-05 C0 baseline 代码迁移与定位

记录人：赵启行

阶段：C0 baseline 整理。

对应任务：将李金航仓库中的代码套入本项目框架，并明确其真实技术定位。

已完成：

- 将迁移代码定位为 C0 Naive RAG / 单文档本地 RAG baseline。
- 明确该部分不是完整 Agentic RAG。
- 保留命令行 Demo、交互式 Demo 和 Gradio 上传文档 Demo。
- 将原根目录 `ARCHITECTURE.md` 移动到 `docs/c0_baseline_architecture.md`，作为 C0 baseline 专项架构说明。

当前 C0 能力：

```text
本地文档解析 -> 固定窗口切块 -> embedding -> 内存向量 Top-K 检索 -> LLM 生成答案
```

当前 C0 不包含：

```text
query rewrite
BM25 / hybrid retrieval
rerank
多轮检索
任务规划
外部工具调用
self-check
批量评测
```

涉及文件：

- `src/agentic_rag/`
- `main.py`（含 `demo` / `ui` 等子命令，`src/agentic_rag/cli/`）
- `docs/c0_baseline_architecture.md`

遗留问题：

- 当前 C0 主要是单文档临时索引，还不是正式知识库检索。
- 后续需要建立 `documents.csv`、`chunks.jsonl` 和持久化向量索引。

## 2026-05-05 C1 Query Rewrite 初版实现

记录人：赵启行

阶段：C1 初版。

对应任务：在 C0 基础上增加 query rewrite，但不混入 C2/C3/C4 能力。

已完成：

- 新增 `src/agentic_rag/rewrite.py`，实现 query rewrite、JSON 解析和检索查询构造。
- 新增 `src/agentic_rag/schemas.py`，固定 `QueryTask`、`RewriteResult`、`EvidenceChunk` 等结构。
- 新增 `src/agentic_rag/logging_utils.py`，支持 JSONL 日志写入。
- 扩展 `src/agentic_rag/pipelines/local_rag.py`：
  - `run_c0_with_index()`
  - `run_c1_with_index()`
  - `retrieve_with_index()`
  - `generate_answer_from_hits()`
- 单文档 C1 演示：`uv run python main.py demo c1 <文档> <问题>`（逻辑在 `cli/demos.py`）。
- 新增 `docs/interface_and_logging_rules.md`，固定 C0-C1 输入输出和日志规范。
- 新增基础测试：
  - `tests/test_rewrite.py`
  - `tests/test_pipeline_schema.py`

C1 当前边界：

- 只新增 query rewrite。
- 不包含 BM25。
- 不包含 rerank。
- 不包含多轮检索。
- 不包含任务规划。
- 不包含工具调用。
- 不包含 self-check。

运行命令：

```powershell
uv run pytest
uv run ruff check .
```

验证结果：

```text
pytest：6 passed
ruff：All checks passed
```

当前结论：

- C1 的工程接口已经初步打通。
- C1 目前能返回结构化字段，包括 `original_query`、`need_rewrite`、`rewritten_query`、`retrieval_queries`、`retrieved_chunks`、`answer`、`citations`、`latency_ms`、`error`。
- 单元测试只能证明接口能跑，不能证明 C1 有实际效果。

下一步：

- 准备 15-20 条 C1 验收题，包括清晰问题、模糊问题、口语化问题。
- 用同一知识库分别跑 C0 和 C1。
- 比较 Recall@5、Answer Correctness、Citation Accuracy、Latency 和 Token Usage。

## 2026-05-05 最小样例文档测试

记录人：赵启行

阶段：单文档链路验证。

对应任务：先用一个文档验证解析和切块是否正常。

输入数据：

```text
data/raw/learning_docs/python_basic_sample.md
```

已完成：

- 新增一个 Python 程序设计样例资料文档。
- 验证该文档可以被当前代码解析。
- 验证 chunk 切分可以正常运行。

验证结果：

```text
suffix: .md
chars: 834
chunks: 2
```

当前结论：

- 已跑通：单个文档 -> 文档解析 -> 文本切块。
- 尚未跑通完整链路：文档 -> embedding -> 向量检索 -> C0/C1 问答。

限制原因：

- 本地 `.env` 当时缺少 `ARK_API_KEY` 和 `DEEPSEEK_API_KEY`，因此无法真实调用 embedding 和 LLM。

后续可运行命令：

```powershell
uv run python main.py demo c1 "data/raw/learning_docs/python_basic_sample.md" "切片咋取中间几个元素？"
```

注意：

- 该样例文档只是最小测试材料，不是正式知识库。
- 正式实验前还需要补充多份学习资料、技术文档、表格数据和代码片段。

## 2026-05-05 C1 单文档真实运行测试

记录人：赵启行

阶段：C1 单文档链路验证。

对应任务：在已配置 `ARK_API_KEY` 和 `DEEPSEEK_API_KEY` 后，用最小样例文档真实跑通 C1。

运行命令：

```powershell
uv run python main.py demo c1 "data/raw/learning_docs/python_basic_sample.md" "切片咋取中间几个元素？"
```

输入数据：

```text
data/raw/learning_docs/python_basic_sample.md
```

运行结果：

```text
run_id: c1-1777986883038-3d80a4d4
config: c1_rewrite
original_query: 切片咋取中间几个元素？
need_rewrite: true
rewrite_type: colloquial
rewritten_query: 在Python中，如何通过切片操作获取列表或字符串的中间几个元素？
log_path: runs/logs/c1_rewrite/run_logs.jsonl
error: 空
```

检索结果：

```text
Top-1 chunk_id: python_basic_sample::chunk_0000
Top-1 score: 0.5554675388005307
Top-1 内容: Python 列表切片语法、start/stop/step 说明和 nums[1:4] 示例
```

答案质量初步判断：

- 查询改写合理：原问题是口语化表达，C1 将其改写为更明确的 Python 切片检索问题。
- 检索结果合理：Top-1 命中列表切片相关证据。
- 答案基本正确：回答解释了 `list[start:stop]`，并给出 `nums[1:4]` 得到 `[1, 2, 3]` 的示例。
- 引用基本可用：答案引用了 `python_basic_sample::chunk_0000`，该 chunk 能支撑答案。

性能与 token 记录：

```text
latency_ms: 9429
query_rewrite prompt_tokens: 257
query_rewrite completion_tokens: 78
query_rewrite total_tokens: 335
answer_generation prompt_tokens: 512
answer_generation completion_tokens: 126
answer_generation total_tokens: 638
total_tokens: 973
```

发现的问题：

- 当前 `citations` 字段会默认列出检索到的 Top-K chunk，本次包含 `chunk_0000` 和 `chunk_0001`。
- 但答案实际只引用并依赖 `chunk_0000`。
- 后续做 Citation Accuracy 时，最好优化为“只输出实际支撑答案的 chunk”，或者在评测时区分 retrieved evidence 和 final citations。

当前结论：

- C1 单文档真实链路已经跑通。
- 本次样例中，C1 成功完成 query rewrite、向量检索、答案生成、引用输出和 JSONL 日志保存。
- 这只能证明 C1 单例运行成功，不能证明 C1 整体效果优于 C0。

下一步：

- 用同一问题跑 C0，比较 C0 与 C1 的 Top-K 检索结果和答案。
- 准备 15-20 条 C1 验收题，重点覆盖清晰问题、模糊问题、口语化问题。
- 统计 C0/C1 的 Recall@5、Answer Correctness、Citation Accuracy、Latency 和 Token Usage。

## 2026-05-05 文档整理与仓库同步

记录人：赵启行

阶段：项目文档清理。

已完成：

- 更新根目录 `README.md`，写清楚项目状态、C0-C4 配置、运行方式、测试方式和下一步。
- 更新 `docs/README.md`，明确 docs 目录导航。
- 将 `team_roles.md` 合并进 `collaboration_workflow.md`。
- 删除独立的 `docs/team_roles.md`。
- 更新 `docs/directory_rules.md`，移除旧文档引用。
- 将 C0 架构文档从根目录移动到 `docs/c0_baseline_architecture.md`。

相关提交：

```text
2dc35f4 feat: add c1 query rewrite workflow
5991526 docs: update project readme
5fa41c9 docs: move c0 architecture into docs
c8843a9 docs: update c0 architecture references
```

当前仓库状态：

```text
main...origin/main
```

当前结论：

- 项目根目录更清爽。
- docs 目录成为协作、接口、架构、实验记录的统一入口。
- 当前 README 已能作为组员 clone 后的第一入口。

## 2026-05-06 C0/C1 20 题批量实验

记录人：赵启行

阶段：C0/C1 小规模对比实验。

对应任务：用同一知识库、同一 20 条测试题分别运行 C0 Naive RAG 和 C1 Query Rewrite RAG，输出结构化 JSONL 日志和 CSV 结果表。

运行命令：

```powershell
uv run ruff check .
uv run pytest
uv run python run_batch_experiments.py
```

输入数据：

```text
data/processed/documents.csv
data/testset/questions.csv
data/testset/references.csv
```

本次知识库：

```text
documents.csv: 23 条文档记录
chunks.jsonl: 475 个 chunk
```

输出文件：

```text
runs/logs/c0_naive/run_logs.jsonl
runs/results/c0_results.csv
runs/logs/c1_rewrite/run_logs.jsonl
runs/results/c1_results.csv
data/processed/chunks.jsonl
```

本次实验边界：

- C0：纯向量检索 + Top-K 证据 + 答案生成。
- C1：在 C0 基础上只新增 query rewrite。
- 本次未开启 BM25、hybrid retrieval、rerank、多轮检索、self-check 和工具调用。
- 若旧的 `run_logs.jsonl` 已存在，脚本会先备份为 `run_logs.before_batch_*.jsonl`，再写入本次新日志。

基础验证结果：

```text
ruff: All checks passed
pytest: 15 passed
```

批量运行结果：

| 配置                 | 日志行数 | 结果行数 | 错误数 | 预期文档命中 | 平均延迟 | 平均 token |
| -------------------- | -------: | -------: | -----: | -----------: | -------: | ---------: |
| C0 Naive RAG         |       20 |       20 |      0 |        17/20 |  7441 ms |        915 |
| C1 Query Rewrite RAG |       20 |       20 |      0 |        18/20 | 11073 ms |       1328 |

未命中预期文档的问题：

```text
C0 未命中：Q005、Q007、Q013
C1 未命中：Q005、Q013
```

初步观察：

- C1 相比 C0 多命中 1 题，主要改善了 Q007。
- C1 平均延迟和 token 消耗高于 C0，这是 query rewrite 带来的额外成本。
- Q005 和 Q013 在 C0/C1 下都没有命中预期文档，是后续失败案例分析的重点。
- 当前结果只能作为初版对比，不宜直接写成正式结论。

重要限制：

- `references.csv` 中的 `evidence_chunk_id` 目前仍为 `pending`，因此本次只能做文档级命中粗评估，不能严格计算 chunk 级 Recall@K 和 Citation Accuracy。
- `top_contains_expected_doc` 只判断 Top-K 中是否出现参考文档，不代表答案一定正确。
- 工具型任务 Q016-Q019 目前仍由 C0/C1 以文本检索方式回答，不代表 C4 工具调用能力。

本次新增/修改：

```text
run_batch_experiments.py
src/agentic_rag/pipelines/local_rag.py
data/processed/chunks.jsonl
```

当前结论：

- C0/C1 的同知识库、同测试集批量实验已经跑通。
- C1 的初步收益存在，但幅度不大，需要继续通过人工评分、gold chunk 标注和失败案例分析确认。
- 下一阶段不应急着堆 C3/C4 功能，应先把 C0/C1/C2 的评测规范做扎实。

## 2026-05-06 C1 Query Rewrite 一次优化

记录人：赵启行

阶段：C1 内部优化，但不作为正式消融实验。

对应任务：只在 C1 边界内进行一次 query rewrite 优化，不引入 BM25、rerank、self-check、多轮检索或工具调用。

优化目标：

1. Prompt v2：让改写结果更像检索 query，而不是普通聊天问句。
2. 多候选 query：从单个 `rewritten_query` 扩展为 `rewritten_queries`，支持语义 query、关键词 query 和实体/文件/代码相关 query。
3. 保守改写：新增 `rewrite_confidence`，当置信度不足或原问题已经清晰时，不进行改写，避免乱改写导致检索劣化。

涉及文件：

```text
src/agentic_rag/schemas.py
src/agentic_rag/rewrite.py
src/agentic_rag/pipelines/local_rag.py
prompts/query_rewrite_prompt.md
configs/c1_rewrite.yaml
run_batch_experiments.py
docs/interface_and_logging_rules.md
tests/test_rewrite.py
```

边界说明：

- 本次不加入术语别名表。
- 本次不做 C1 内部消融实验。
- 本次优化后仍统一称为 `C1`，不在主线中拆分 C1 子版本。
- 正式实验中仍然只比较 `C0 -> C1 -> C2 -> C3 -> C4`。
- 当前 C1 只是更强的 query rewrite，不代表 C2/C3/C4 能力。

后续验证方式：

```powershell
uv run ruff check .
uv run pytest
uv run python run_batch_experiments.py
```

验证重点：

- C1 日志中应出现 `rewrite_confidence` 和 `rewritten_queries`。
- `retrieval_queries` 应保留原问题，并追加多个候选检索 query。
- 清晰问题不应被强行改写。
- 重新跑同一 20 题后，再比较 C0 与 C1 的文档命中、人工答案质量、引用可信度、延迟和 token 成本。

## 2026-05-06 C1-final 重跑结果与分析

记录人：赵启行

阶段：C1 优化后复测。

说明：本节仅在实验报告中使用 `C1-final` 这个名称，用于区分“优化前 C1”和“优化后 C1”。项目主线、README 和配置中仍统一称为 `C1`。

运行目的：

- 验证 C1 的一次优化是否真正提升文档级命中。
- 观察多候选 query 和保守改写判断带来的延迟与 token 成本。
- 分析 C1 的有效任务类型和收益边界。

运行命令：

```powershell
uv run ruff check .
uv run pytest
uv run python run_batch_experiments.py
```

运行说明：

- 本次仍使用同一知识库、同一 20 条测试题。
- C0 不变。
- C1-final 只改变 query rewrite，不启用 BM25、hybrid retrieval、rerank、多轮检索、self-check 或工具调用。
- 首次完整运行时，部分 DeepSeek 调用耗时异常，导致批量脚本超时；随后对缺失/错误题进行了补跑，并整理为每个配置 20 行干净日志和 CSV。
- 为避免后续实验被单次 API 调用长时间阻塞，已为 DeepSeek 客户端增加 60 秒超时，为 Ark embedding 增加轻量重试。

输出文件：

```text
runs/logs/c0_naive/run_logs.jsonl
runs/results/c0_results.csv
runs/logs/c1_rewrite/run_logs.jsonl
runs/results/c1_results.csv
```

基础检查：

```text
ruff: All checks passed
pytest: 18 passed
C0 日志行数: 20, error: 0
C1 日志行数: 20, error: 0
```

总体结果：

| 配置     | 文档级命中 | 未命中题目       | 平均延迟 | 平均 token | 平均检索 query 数 |
| -------- | ---------: | ---------------- | -------: | ---------: | ----------------: |
| C0       |      17/20 | Q005、Q007、Q013 |  7382 ms |        962 |              1.00 |
| 旧 C1    |      18/20 | Q005、Q013       | 11073 ms |       1329 |              1.75 |
| C1-final |      19/20 | Q013             | 37060 ms |       1905 |              3.95 |

按任务类型统计：

| 任务类型              |  C0 | C1-final | 观察                                                            |
| --------------------- | --: | -------: | --------------------------------------------------------------- |
| simple_qa             | 4/4 |      4/4 | 清晰事实题中 C1 没有明显额外收益。                              |
| fuzzy_query           | 2/4 |      4/4 | C1-final 的主要收益来自模糊/口语化问题。                        |
| multi_doc             | 4/4 |      4/4 | 本轮多文档题 C0 已能命中，C1 提升不明显。                       |
| table_analysis        | 2/3 |      2/3 | Q013 仍失败，说明仅 query rewrite 不足以解决表格/文件定位干扰。 |
| calculation           | 2/2 |      2/2 | 计算题当前仍按文本检索处理，不代表 C4 工具能力。                |
| code_execution        | 2/2 |      2/2 | 代码题当前仍按文本检索处理，不代表 C4 工具能力。                |
| insufficient_evidence | 1/1 |      1/1 | 当前样例可命中相关材料，但仍需人工判断答案是否保守。            |

关键案例：

1. Q005：C1-final 成功改善。

```text
问题：我看到一篇论文说能让大模型自己判断什么时候去查资料再回答，那篇论文提出了什么方法？
C0 Top 文档：doc_017、doc_011 等，未命中预期 doc_014。
旧 C1 Top 文档：doc_001、doc_017、doc_011 等，仍未命中 doc_014。
C1-final Top 文档：doc_014、doc_011、doc_011、doc_014、doc_011，命中预期 doc_014。
```

原因分析：C1-final 生成了多个更像检索 query 的候选，例如“大模型 自主判断 检索 时机 方法 论文”和“LLM decide when to retrieve before answering paper”，比旧 C1 的单个自然语言改写更容易匹配 Self-RAG 相关资料。

2. Q007：C1-final 相比 C0 改善，但答案仍不够完整。

```text
问题：我们课题组要做 RAG 系统，我应该参考哪些开源项目？
C0 未命中预期文档集合。
C1-final 命中了 RAGFlow 等相关文档。
```

原因分析：多候选 query 能提升“开源项目推荐”类问题的入口检索，但由于 Top-K 中仍混入 RAGAS、论文综述等内容，答案覆盖 Dify、RAGFlow、CrewAI、LangGraph 仍不稳定。该问题后续更适合交给 C2 的 hybrid retrieval / rerank 优化。

3. Q013：C1-final 仍失败。

```text
问题：从 arxiv_agentic_rag_papers_v2.md 中统计论文的类型分布。
预期文档：doc_011。
C1-final Top 文档：doc_022、doc_022、doc_012、doc_022、doc_013。
```

原因分析：虽然 C1-final 明确加入了文件名和“论文类型分布”等关键词，但检索仍被 `agentic_rag_knowledge_crawler.py` 相关 chunk 干扰。该问题不是单纯 query rewrite 可以解决的，更像是 chunk 级排序、文件名过滤、hybrid retrieval 或 rerank 的问题，应进入 C2 分析。

当前结论：

- C1-final 相比 C0 有明确收益，文档级命中从 17/20 提升到 19/20。
- C1-final 相比旧 C1 也有提升，主要解决了 Q005。
- C1-final 的收益高度集中在 fuzzy_query 类型任务，说明 query rewrite 更适合处理表达不规范、口语化、语义模糊的问题。
- C1-final 的代价明显上升，平均延迟和 token 均高于 C0 与旧 C1。
- C1-final 不能解决所有问题。对 Q013 这类受 chunk 干扰、文件定位和排序影响较大的任务，应交给 C2 的检索增强模块继续优化。

可写入后续报告的表述：

```text
C1-final 的实验结果表明，查询改写对模糊表达和口语化问题具有明显帮助，能够提高相关文档命中率；但多候选 query 会带来额外 token 和延迟成本。对于清晰事实题、工具型任务和受 chunk 排序干扰的问题，单独 query rewrite 的收益有限，需要进一步结合 hybrid retrieval、rerank 或工具调用模块。
```

## 2026-05-06 C2 检索三阶段消融实验

记录人：李金航

阶段：C2 Advanced RAG 检索能力消融（在 **C1 query rewrite** 基础上依次叠加：混合检索 → LLM 重排 → 邻接上下文扩展）。

对应任务：在同一知识库、同一测试集（`questions.csv` 前 20 条）上，对比三种检索配置的收益与成本；产物用于结题报告中的「C2 相对 C1 的增量」说明。

运行命令：

```powershell
cd <含 pyproject.toml 的项目根>
uv sync
uv run python run_c2_retrieval_ablation.py --phase all
```

运行说明：

- 本次使用脚本默认参数：`--limit 20`、`--top-k 5`、`--rerank-pool 20`、`--rerank-backend llm`、`--dense-weight 0.6`、`--bm25-weight 0.4`；阶段 3 邻接扩展 `--neighbors 1`。
- 首次构建索引时对知识库全文切块并调用方舟 embedding；日志显示共 **475** 个文本块，已向量化并写入 **Chroma**（集合 `ragkb_kb_<指纹>`，`CHROMA_PERSIST_DIRECTORY`；后续复跑可跳过长时间 embedding）。
- 三组实验依次执行，每组 20 题，日志与结果表按阶段分目录/分文件写出。

输入数据：

```text
data/processed/documents.csv
data/processed/chunks.jsonl（由索引构建流程维护）
data/testset/questions.csv（前 20 条）
data/testset/references.csv
```

输出文件：

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

汇总结果（与终端摘要、`c2_ablation_summary.json` 一致）：

| 阶段 key                               | 题数 | 错误 | 文档级命中 | 命中率 | 均延迟 (ms) | 均 total_tokens | 均检索 query 数 |
| -------------------------------------- | ---: | ---: | ---------: | -----: | ----------: | --------------: | --------------: |
| `c2_stage1_c1_hybrid`                |   20 |    0 |      20/20 | 100.0% |       10715 |            2130 |            3.90 |
| `c2_stage2_c1_hybrid_rerank`         |   20 |    0 |      20/20 | 100.0% |       16130 |           13085 |            4.10 |
| `c2_stage3_c1_hybrid_rerank_context` |   20 |    0 |      19/20 |  95.0% |       13975 |           13536 |            3.85 |

初步观察：

- 打开 **LLM 重排**（阶段 2）后，平均 token 与延迟显著高于阶段 1，符合「多一次 DeepSeek 调用」的预期；文档级命中率本轮仍为 20/20。
- **邻接上下文扩展**（阶段 3）在平均延迟上介于阶段 1 与阶段 2 之间，但文档级命中降为 **19/20**；未命中题为 **Q013**（表格/指定文件统计类，与前期 C1 分析中「chunk 干扰与文件定位」难点一致），需在后续报告中单独做失败案例说明，不宜仅归因于「上下文扩展」本身。
- `gold_chunk_hit` / `gold_chunk_recall_rate` 在汇总中仍受限：`evidence_chunk_id` 多为 `pending`，chunk 级严格指标待标注补齐后再解读。

重要限制（与既有实验口径一致）：

- **文档级命中**来自 `top_contains_expected_doc` 与 `references.csv` 的 `evidence_doc_id`，不代表答案语义正确或引用充分。
- **Token** 以接口返回的 `usage` 为准（当前工程不对缺失用量做估算）；明细见各阶段 CSV 与 JSONL 中 `token_usage`。

本次涉及脚本（仅列入口，具体改动以 Git 为准）：

```text
run_c2_retrieval_ablation.py
run_batch_experiments.py（C2 结果行字段复用）
src/agentic_rag/pipelines/local_rag.py
```

下一步：

- 对照三份 CSV 与 `c2_ablation_report.md`，整理阶段 1→2→3 的成本—收益表述；重点复核 **Q013** 在阶段 3 的 Top-K 与答案。
- 补全 `evidence_chunk_id` 后重算 chunk 级指标；必要时固定随机种子或单独记录 rerank 模型版本以便复现。

### C2 三阶段：答案正确率（LLM 自动化测试 · 正确性待人评）

> **声明**：下表中的「满分 / 部分对 / 错误 / 平均分」均为 **DeepSeek 按 `judge_rule` 自动给出的流水线测试结果**，**不等于**已人工核验的最终正确率，**不能单独作为结题结论**。正式结论须在组成员 **人工按同一 `judge_rule` 抽样或全量标注** 后更新；届时对比人评与 AI 评，用于评估 **AI 评判模块**及后续 **AI 自规划 / 自检** 链路的可信度（与赵启行在「当前待办」中强调的 Answer Correctness 人工复核口径一致）。

记录人：李金航

阶段：在赵启行定义的批量评测表（文档级命中、延迟、token、检索 query 数）基础上，补齐 **Answer Correctness** 的**可重复自动化测试**，并将评判逻辑收口为独立代码模块。

说明：

1. **结果来源**：仓库当前仅有 **C2** 检索三阶段消融 CSV（`c2_stage{1,2,3}_*_results.csv`）。口语中的「三次消融」若无单独 **C3 Agentic** 跑批文件，则本节默认对应 **C2 阶段 1→2→3**，而非 C3 代码路径。
2. **检索侧指标**：与赵启行记录 C0/C1-final 时相同的 CSV 字段——`top_contains_expected_doc`、`latency_ms`、`total_tokens`、`retrieval_query_count`。
3. **答案「正确率」列（自动化）**：调用 DeepSeek，按 `data/testset/references.csv` 中每条题的 **`judge_rule`**（及参考答案要点）对 **`answer`** 打 **0 / 0.5 / 1** 分；Prompt 见 `prompts/answer_judge_prompt.md`。评判实现位于独立包 **`src/agentic_rag/evaluation/ai_answer_judge/`**（详见 `docs/evaluation_ai_judge.md`）。入口脚本：`run_c2_ablation_answer_accuracy.py`（单文件评判：`run_score_answer_accuracy.py`）。逐题明细：`runs/results/c2_stage*_results_scored.csv`；机器摘要：`runs/results/c2_ablation_answer_accuracy.json`、`runs/results/c2_ablation_answer_accuracy_report.md`。
4. **评判 token**：评分调用单独计费，**不计入** RAG 管线 JSONL/CSV 中的 `total_tokens`。

对应任务：C2 检索三阶段消融复现、指标对齐赵启行批量实验写法，并落地 **可复用的 AI 评判模块**与批量打分脚本。

已完成：

- 跑通 `run_c2_retrieval_ablation.py --phase all`（20 题 × 三阶段），产出三份阶段 CSV、`c2_ablation_summary.json`、`c2_ablation_report.md`，并在本节上方记录检索侧汇总。
- 实现 **独立子模块** `agentic_rag.evaluation.ai_answer_judge`：按题库 `judge_rule` 调用 LLM 评判，与 RAG 生成链路解耦，便于后续与人评对照。
- 编写 `run_score_answer_accuracy.py`、`run_c2_ablation_answer_accuracy.py`，生成 `*_scored.csv` 及聚合报告；字段设计与 `interface_and_logging_rules.md` 第 8 节、`docs/evaluation_ai_judge.md` 对齐。
- 在本文档标明：**当前正确性数字为自动化测试结果**，最终正确性 **等待后续人工标注验证**。

汇总表（同一测试集 20 题；**以下为 LLM 评判测试结果**，待人评）：

| 阶段                       | 文档级命中 | 未命中题 | 满分(1.0) | 部分对(0.5) | 错误(0) | 平均得分 | 均延迟(ms) | 均 total_tokens | 均检索 query 数 | 评判消耗 token |
| -------------------------- | ---------: | -------- | --------: | ----------: | ------: | -------: | ---------: | --------------: | --------------: | -------------: |
| 阶段1：C1+混合检索         |      20/20 | —       |         5 |           9 |       6 |    0.475 |      10715 |            2130 |            3.90 |          14385 |
| 阶段2：C1+混合+重排        |      20/20 | —       |         9 |           7 |       4 |    0.625 |      16130 |           13085 |            4.10 |          14790 |
| 阶段3：C1+混合+重排+上下文 |      19/20 | Q013     |         1 |           1 |      18 |    0.075 |      13975 |           13536 |            3.85 |          11820 |

解读注意：

- **文档级命中高 ≠ 答案得分高**：赵启行在「2026-05-06 C0/C1 批量实验」一节已强调，`top_contains_expected_doc` 只反映检索是否捞到参考文档，不代表生成答案满足 `judge_rule`。
- **AI 评分数高或低 ≠ 最终正确**：本节分数为自动化测试输出；是否采纳须经人工标注对照。
- 阶段 2 在**平均分与满分条数**上优于阶段 1，与「加入 LLM 重排改善排序」的直觉一致（仍需结合题型拆分细读 `_scored.csv`）。
- **阶段 3 平均分极低**与文档级命中（19/20）存在张力：同一批题下，邻接扩展可能使答案更长、更多「证据不足」类表述，从而触发规则扣分；亦不能排除 **LLM 评判随机性**。在人工复核前，不宜将该平均分单独写入对外结论。

本次新增/涉及文件：

```text
src/agentic_rag/evaluation/ai_answer_judge/
src/agentic_rag/evaluation/answer_judge.py（兼容转发）
docs/evaluation_ai_judge.md
run_c2_ablation_answer_accuracy.py
run_score_answer_accuracy.py
prompts/answer_judge_prompt.md
docs/interface_and_logging_rules.md（§8 AI 评判模块输出）
```

## 2026-05-11 Agent 编排增强、全库检索默认化与知识库入库闭环

记录人：李金航

阶段：课题四工程能力补强 —— **新增多层级 Agent 编排**（新写调度与入口层）、全库 Chroma 对齐批量实验、交互与大段输入可用性、稳定性修复。

### 背景与目标

- **编排层（`orchestration/` + `main.py agent` 接线 + `deep_planning` 中除既有 RAG 工具封装外的调度逻辑）为重新实现**，不是仓库里历史就有的完整子系统；在「第一层规划 → 第二层 Deep Agent + RAG 工具 → 第三层研判」的**目标形态**上，**复用**既有能力：`experiment.run_document_rag` / 新增的 `run_knowledge_base_rag`、`kb_index_builder`、`RunProfile` 预设、Chroma、以及评测里 JSON 评判思路在编排侧的 **`kb_grounding`** 变体等。
- 在上述新增编排上，明确三层职能边界（解析填槽 / 工具执行 / 调度裁决），并与评测侧 judge 思路对齐可选「检索摘录 vs 答复」核验。
- 默认检索应与批量实验一致：**`data/processed/documents.csv` 定义的全库向量索引（Chroma）**；`data/testset/references.csv` 仍为**评测对照**，不充当向量库清单。
- 支持用户增量文档登记并触发索引重建，便于「自然语言 + 路径」一类任务在第二层通过工具闭环。

### 已完成（实现摘要）

| 模块                                                                                                                 | 内容                                                                                                                                                                |
| -------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `orchestration/*`、`deep_planning/agent_cli.py`、`deep_planning/agent_runner.py`（等与编排入口直接相关的部分） | **本次重写/新增**：调度循环、CLI、`OrchestrationConfig`、与 Deep Agents / LangGraph 的接线方式；**复用**下层 RAG 与工具工厂封装。                     |
| `experiment/runner.py`                                                                                             | 新增 `run_knowledge_base_rag`，与 `kb_index_builder.load_or_build_knowledge_index` 共用全库索引。                                                               |
| `experiment/kb_ingest.py`                                                                                          | `ingest_local_file_to_kb`：追加 `documents.csv`、复制至 `data/raw/user_docs/`（默认）、`force_rebuild` 写回 Chroma。                                        |
| `cli/app.py`                                                                                                       | 子命令 `main.py kb ingest …`（`--no-copy` / `--no-rebuild` 等）。                                                                                            |
| `deep_planning/tools_factory.py`                                                                                   | `topic4_rag_query` 默认全库；绑单文档时用 `run_document_rag`；工具 `topic4_kb_ingest`（路径须在工程根内）。可选 `sandbox_exec_python`（视 `SANDBOX_*`）。 |
| `orchestration/*`                                                                                                  | `kb_grounding`、`loop` 中可选对齐核验与研判串联；`OrchestrationConfig` 开关。                                                                                 |
| `config.py`                                                                                                        | `PROJECT_ROOT`；`.env` 优先覆盖 shell 空变量；`DEEPSEEK_API_KEY` 可回退 `OPENAI_API_KEY`。                                                                  |
| `orchestration/loop.py` + `agent_cli.py`                                                                         | 交互默认**多行**：粘贴后以单独一行 `end`/`END` 提交；`--single-line` 恢复单行；`--once-file` / `--stdin` 适合整表 `questions.csv`。               |
| `rag/chroma_store.py`                                                                                              | 对 Chroma 读写加 `RLock`，缓解 LangGraph 并发工具导致的 `Collection … does not exist`。                                                                        |
| `session_planner.py` / `agent_runner.py` / `judge_layer.py`                                                    | 刷新系统提示词，固化三层 Skill 边界。                                                                                                                               |
| `.cursor/skills/topic4-orchestration-layers/SKILL.md`                                                              | 编排三层职能说明，供后续改提示词或协作对照。                                                                                                                        |

### 典型运行命令（无密钥示例）

```powershell
uv sync --group agent
uv run python main.py kb ingest path\to\new_doc.md --title "备注标题"
uv run python main.py agent --once-file data\testset\questions.csv
```

### 注意事项（实验口径）

- **不得在本文档粘贴 API Key 或完整 `.env`。**
- PowerShell 下 **`PS>` 直接粘贴 CSV 行会被当成脚本解析**；大段内容应通过 **`main.py agent` 启动后的多行模式**、或 **`--once-file`** / **`--stdin`** 传入 Python 进程。
- 第三方警告：`langgraph` / LangChain 可能出现 `allowed_objects` 弃用提示，与本次逻辑无关时可暂缓处理。

### 遗留 / 后续可选项

- 图形化「问答界面」与 `main.py agent` 对接需单独 UI 工程；当前默认仍为终端交互。
- Deep Agents 官方远端沙箱（Modal 等）未接入；本地沙箱为 subprocess + 临时目录。

### 编排调试补充（同日会话整理）

**现象与原因（非「进程死锁」为主）**

- **`[index]` 打印后长时间无新标题**：每次工具调用 `topic4_rag_query` 都会进入 `load_or_build_knowledge_index`；命中 Chroma 时仍会先完成同步逻辑，随后还有检索、（部分管线）改写与生成等步骤；**默认无流式输出**，终端像在空转。
- **第三层研判之后再度刷屏 `[index]`**：第三层若返回 `continue_execute`，编排会在**同一轮规划下再次** `invoke` 第二层 Deep Agent，大批量 CSV 任务会再次触发**大量** `topic4_rag_query`，表象为「研判结束后又卡一轮」。
- **PowerShell / 终端偶发半截行、两行粘在一起**：高频 `print` 与长输出缓冲可能导致行尾混杂；与「索引逻辑错误」未必等价。
- **知识库对齐核验 `grounded=false`**：表示「模型最终答复要点」与「工具返回的 evidence_excerpt」对齐不足，用于自检；不等同于编排调度失效。

**已落地修改（代码）**

- `orchestration/loop.py`：研判触发「继续执行」时，在下一次第二层调用前打印说明，避免误判卡死。
- `experiment/kb_index_builder.py`：同一 Chroma 集合的缓存命中日志**同进程只打一次**；增加 **`_KB_INDEX_MEMORY`**，同一 fingerprint 的全库 `SimpleVectorIndex` **内存复用**，避免每次 RAG 重复从 Chroma 还原大块数据。
- `deep_planning/agent_cli.py`：对 **`--once` / `--once-file` / `--stdin`** 单次注入，默认 **`max_orchestration_rounds=1`、`max_execute_retries_per_round=1`**，避免研判触发整轮重复执行；需要旧行为时加 **`--orchestrate-repeat`**，并可配合 `--max-rounds`、`--max-execute-retries`。
- `main.py` 顶部用法说明中补充 `--orchestrate-repeat` 提示。

**工作流提醒（题目文件 + 入库文件）**

- **必须先入库再问答**：`uv run python main.py kb ingest <文件>` 完成清单与索引重建后，再 `uv run python main.py agent --once-file data\testset\questions.csv`（或交互里先 `topic4_kb_ingest` 再 `topic4_rag_query`）。顺序反了则首轮答题看不到新文档。

**仍建议后续改进（未实现或仅部分缓解）**

- 第二层 / 工具链：**可选流式输出或统一进度回调**（LangChain callback），长任务中心跳可观测。
- 第三层研判：对「整表 CSV 一次性作答」类任务，提示词或策略上**倾向一次 `complete`**，减少无意义的 `continue_execute`（已通过 CLI 默认限制兜底）。
- Windows 终端：必要时对关键 `print` 使用 **`flush=True`** 或集中日志，减少行交织观感。
- **评测口径**：`kb_grounding` 与题库 rubric 不同；长答复 vs 单题摘录核验容易判 `grounded=false`，需在实验报告中区分「调度」与「引用覆盖」语义。

---

## 2026-05-12 Agent 规划链增强、MarkItDown 读文件工具与编排扩展钩子

记录人：李金航

阶段：课题四 —— 规划层与第二层工具链补强（可扩展接口）、知识库登记事实注入、多格式文件转 Markdown；架构文档与 Skill 同步。

### 背景与目标

- 利用与 **C1 同源**的 `rewrite_query` 辅助第一层理解混杂自然语言中的检索意图（可选开关，多一次 DeepSeek 调用）。
- 以 **`documents.csv` 为准**向第二层注入「单文件是否已登记」等**确定性**说明，避免模型臆测「是否已向量化」；与第一层 JSON 字段 **`kb_mutation_intent`**（`none` / `ingest_if_missing` / `ingest_force`）及 **`needs_retrieval_tools`** 对齐。
- 接入 [Microsoft MarkItDown](https://github.com/microsoft/markitdown) 作为第二层工具 **`topic4_file_to_markdown`**（工程根内路径、字节上限、插件默认关闭），与既有 `documents.parse_path` 的 RAG 切块链**并行**，不替换默认解析。
- 支持在创建第二层 Agent 时 **合并额外 LangChain 工具**（`OrchestrationHooks.extend_agent_tools` + `build_topic4_deep_agent(..., additional_tools=...)`），便于后续接 Cube/E2B 等远端沙箱或自研工具。
- 在 `config.py` 中备忘 **CubeSandbox**（KVM MicroVM、兼容 E2B API）为可选强隔离方案，与本仓库本地 subprocess 沙箱**无自动对接**。

### 已完成（实现摘要）

| 模块                                                              | 内容                                                                                                                                                                          |
| ----------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `experiment/kb_inventory.py`                                    | `file_path_registered_in_documents_csv`、`relative_path_under_project`：清单比对（路径规范化）。                                                                          |
| `orchestration/planning_extensions.py`                          | `PlanningEnrichInput`、`format_query_rewrite_block`、`kb_execution_notes_for_layer2`；与 `rewrite` / 清单逻辑解耦。                                                   |
| `orchestration/types.py`                                        | `OrchestrationConfig`：`enable_planning_query_rewrite`、`planning_rewrite_prompt_file`、`enable_kb_inventory_hints`。                                                 |
| `orchestration/registry.py`                                     | `OrchestrationHooks.extend_agent_tools`；保留 `planning_context_enricher`。                                                                                               |
| `orchestration/loop.py`                                         | 第一层前可选改写注入与自定义 enricher；第二层消息附加 KB 登记备注；合并 `additional_tools`；移除未使用的 `sys` 导入。                                                     |
| `deep_planning/session_planner.py`                              | `SessionPlan.kb_mutation_intent`、`planning_preamble`；L1 提示词扩展；`compose_layer2_user_message` 支持 `kb_execution_notes` 与 `needs_retrieval_tools` 分流说明。 |
| `deep_planning/agent_cli.py`                                    | `--planning-rewrite`、`--planning-rewrite-prompt`、`--no-kb-inventory-hints`。                                                                                          |
| `deep_planning/agent_runner.py`                                 | `build_topic4_deep_agent(..., additional_tools=...)`；系统提示补充 `topic4_file_to_markdown`。                                                                            |
| `deep_planning/tools_factory.py`                                | 工具**`topic4_file_to_markdown`**；`dependency-groups.agent` 增加 **markitdown** 等传递依赖。                                                                 |
| `tools/markitdown_tool.py`、`tools/__init__.py`               | MarkItDown 封装与安全边界（`MARKITDOWN_MAX_FILE_BYTES`）。                                                                                                                  |
| `config.py`                                                     | `MARKITDOWN_MAX_FILE_BYTES`；CubeSandbox 运维备忘注释。                                                                                                                     |
| `orchestration/__init__.py`                                     | 导出 `PlanningEnrichInput`、`PlanningContextEnricher`、`format_query_rewrite_block`、`kb_execution_notes_for_layer2`。                                                |
| `.cursor/skills/topic4-orchestration-layers/SKILL.md`           | 第二层工具表、`extend_agent_tools`、Skill 必要性说明。                                                                                                                      |
| `docs/ARCHITECTURE.md`                                          | §2.4 `tools/` 实装说明；§2.9 工具表与依赖组；§2.11 沙箱/MarkItDown/Cube 备忘；§5 修订记录。                                                                             |
| `tests/test_kb_inventory.py`、`tests/test_markitdown_tool.py` | 清单与 MarkItDown 封装单测。                                                                                                                                                  |

### 典型命令（节选）

```powershell
uv sync --group agent
uv run python main.py agent --planning-rewrite
uv run python main.py agent --planning-rewrite --planning-rewrite-prompt prompts\query_rewrite_prompt.md
uv run python main.py agent --no-kb-inventory-hints
```

### 注意事项

- **MarkItDown** 部分格式可能需额外可选依赖（官方文档）；当前工具内 `enable_plugins=False`，复杂 Office 若失败应在实验记录中注明环境与依赖版本。
- **CubeSandbox** 需独立 Linux/KVM 部署；内存与规格以官方 README 为准，本仓库不内置客户端。
- **extend_agent_tools**：在每次**重建**第二层 Agent 时调用；若需每轮动态换表，需在编排策略上显式重建 Agent 或扩展钩子语义。

### 本次新增/涉及文件（路径清单）

```text
src/agentic_rag/experiment/kb_inventory.py
src/agentic_rag/orchestration/planning_extensions.py
src/agentic_rag/orchestration/types.py
src/agentic_rag/orchestration/registry.py
src/agentic_rag/orchestration/loop.py
src/agentic_rag/orchestration/__init__.py
src/agentic_rag/deep_planning/session_planner.py
src/agentic_rag/deep_planning/agent_cli.py
src/agentic_rag/deep_planning/agent_runner.py
src/agentic_rag/deep_planning/tools_factory.py
src/agentic_rag/tools/__init__.py
src/agentic_rag/tools/markitdown_tool.py
src/agentic_rag/config.py
pyproject.toml / uv.lock（agent 组含 markitdown）
.cursor/skills/topic4-orchestration-layers/SKILL.md
docs/ARCHITECTURE.md
tests/test_kb_inventory.py
tests/test_markitdown_tool.py
```

---

## 2026-05-17 C3/C4 统一客户端、Agent Runtime、多文档入库与传入检查

记录人：李金航
阶段：课题四 —— 产品化客户端与 Runtime 骨架；多文档 Chroma 子集检索；传入文件治理与审计日志。

### 背景与目标

- 提供 **`main.py client`** 统一入口（Gradio 默认 + `--console`），与 `main.py agent` **共用**三层编排内核，避免第三套推理路径。
- 支持「开始会话」前绑定**多份本地文档**（含盘外路径复制到 `data/raw/user_docs/`），会话内按 **doc_id 子集**检索，而非只能全库。
- 传入前展示**检查表**（文件名、绝对路径、SHA256 前缀、与库内重复关系）；**内容相同**时复用已有 doc_id，避免重复 CSV 行与无意义 `force_rebuild`。
- 客户端操作写入 **`runs/logs/audit/global_audit.jsonl`**，不参与模型规划。
- 抽取 **Agent Runtime**（`QueryEngine`、REPL、headless、governance），便于后续 MCP/无头批测扩展。

### 已完成（实现摘要）

| 模块                                            | 内容                                                                                                                                      |
| ----------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `cli/c34_client.py`                           | C3/C4 档位、`prepare_document_scope_from_input`、`run_c34_turn` → `QueryEngine`；Gradio 6 `role/content` 对话格式。              |
| `documents/multi_doc.py`                      | 路径/自然语言解析、`SessionDocumentScope`、`build_session_document_scope`（含去重入库逻辑）。                                         |
| `documents/ingest_inspector.py`               | `inspect_document_paths`、`format_ingest_report_markdown`、`resolve_session_doc_ids`；`duplicate_content_in_kb` 默认复用 doc_id。 |
| `experiment/runner.py`                        | `allowed_doc_ids` 过滤；终端 `[rag] 知识库检索限定 doc_id：…`。                                                                      |
| `pipelines/local_rag.py`                      | 混合/稠密检索按 `allowed_doc_ids` 过滤 chunk。                                                                                          |
| `deep_planning/tools_factory.py`              | 工具 JSON 增加 `allowed_doc_ids`、`retrieved_doc_ids`；`evidence_excerpt` 标注 `doc_id=`。                                        |
| `deep_planning/agent_runner.py`               | 绑定 doc_id 子集时提示核对 `retrieved_doc_ids`。                                                                                        |
| `orchestration/loop.py`                       | 传入 `kb_doc_ids`、`cli_documents_hint` 至 Agent 构建与 L2 消息。                                                                     |
| `experiment/kb_ingest.py`                     | 批量入库后 `_KB_INDEX_MEMORY.pop(fp)`，避免陈旧内存索引。                                                                               |
| `telemetry/audit_log.py`、`client_hooks.py` | 全局审计 JSONL + 编排层钩子。                                                                                                             |
| `runtime/*`                                   | `cli_router`、`QueryEngine`、`query_loop`、`governance`、REPL、headless、`AppState`/`effects`。                               |
| `tests/test_ingest_inspector.py` 等           | 传入检查、Runtime 相关单测。                                                                                                              |

### 典型命令

```powershell
uv sync --group agent
# Gradio：http://127.0.0.1:7860
uv run python main.py client
uv run python main.py client --console --c3
uv run python main.py client --docs-text "data/raw/tech_docs/dify_readme.md"

# Runtime REPL / 无头（与 client 共用 QueryEngine 包装）
uv run python main.py runtime repl --c3
uv run python main.py runtime headless --tasks data/testset/questions_headless_sample.txt --format json

# 规划前查询改写（CLI 已支持；Gradio client 默认未开）
uv run python main.py agent --c3 --planning-rewrite
```

### 已知问题与排查（客户端多文档）

| 现象                                                  | 原因 / 处理                                                                                                                  |
| ----------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| 检查表 `duplicate_content_in_kb` 仍新建 doc_028/029 | **已修复**：`resolve_session_doc_ids` 跳过重复入库，复用 doc_024 等；需重启 client 加载新代码。                      |
| Agent 称检索到 LangChain 官方文档                     | 常为误判或全库泄漏；核对工具 JSON 的 `retrieved_doc_ids` 与终端 `[rag] 限定 doc_id`；学习指南正文亦含 LangChain 关键词。 |
| `grounded=false`                                    | 第三层 KB 对齐：答复与 `evidence_excerpt` 不一致；区分「调度失败」与「引用不足」。                                         |
| 对话里无法发附件/网址                                 | **未实现**；盘外文件用「开始会话」路径框；网址需先爬取或保存为本地文件入库。                                           |

### 指纹与重复入库（备忘）

- `kb_fingerprint` = CSV 各行 **路径 mtime/size** + 切块/embedding 参数，**不是**文件内容 hash。
- 同内容、不同路径 → 旧逻辑会新增 doc_id；现默认 **SHA256 相同则复用已有 doc_id**，不重建 Chroma。
- 同路径文件修改 → mtime/size 变 → 指纹变 → 需 `force_rebuild`。

### 文档同步

- `docs/ARCHITECTURE.md` §2.10–2.14、§5 修订记录
- `docs/agent_runtime_architecture.md` 完成度表与日志双线
- 后续工具对称化见 **2026-05-18** 条目

### 本次新增/涉及文件（路径清单）

```text
src/agentic_rag/cli/c34_client.py
src/agentic_rag/documents/multi_doc.py
src/agentic_rag/documents/ingest_inspector.py
src/agentic_rag/telemetry/audit_log.py
src/agentic_rag/telemetry/client_hooks.py
src/agentic_rag/runtime/entrypoints/cli_router.py
src/agentic_rag/runtime/engine/query_engine.py
src/agentic_rag/runtime/engine/query_loop.py
src/agentic_rag/runtime/tools/governance.py
src/agentic_rag/runtime/interaction/repl.py
src/agentic_rag/runtime/headless/runner.py
src/agentic_rag/runtime/state/app_state.py
src/agentic_rag/runtime/state/effects.py
docs/ARCHITECTURE.md
docs/agent_runtime_architecture.md
tests/test_ingest_inspector.py
tests/test_runtime_*.py
```

### 仍建议后续改进

- Gradio 暴露「规划前查询改写」勾选项；对话区 **File 上传**（仍无）；**URL** 见 2026-05-18（C4 Agent 动态 Firecrawl，非 Gradio 自动抓取）。
- 编排 hooks 发射 `tool_start`/`tool_end` 结构化事件（非仅审计 JSONL）。
- 清理 `documents.csv` 历史重复 doc_id（可选人工删行 + 一次 `force_rebuild`）。

### Git 痕迹

- 提交：`547f8ae` — `feat(client): C3/C4 统一客户端、多文档入库去重与 Runtime 编排骨架`（已 push `main`）。

---

## 2026-05-18 C4 外部工具对称化：Firecrawl 网页 + 本地文件动态工具族

记录人：李金航
阶段：课题四 —— 第二层工具与第一层填槽对齐「网页 / 本地盘」双通道；统一工具 JSON 外壳；C3 严格不暴露外部工具。

### 背景与目标

- 用户要求：**读取与操作本地文件**应像 **Firecrawl 抓网页**一样，由第二层 Agent **按需动态调用**，而不是拆成 `topic4_read_local_file` + `topic4_file_to_markdown` + `topic4_kb_ingest` 多个易混淆入口。
- **C3** 仍仅 `topic4_list_rag_pipelines` + `topic4_rag_query`；即使配置了 `FIRECRAWL_API_KEY` 也不注册 Firecrawl / 读盘工具。
- **C4** 在检索工具之外，提供对称的两组能力：
  - **网页**：`topic4_firecrawl_scrape` / `topic4_firecrawl_search` / `topic4_firecrawl_scrape_to_kb`（需 Key）
  - **本地**：`topic4_file_read` / `topic4_file_ingest`（读盘 + 入库；MarkItDown 作为工程根内读取后端，不单独暴露工具名）

### 已完成（实现摘要）

| 模块                                     | 内容                                                                                                                                          |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `tools/firecrawl_tool.py`              | `scrape_url` / `search_web`；URL 抽取；`scrape_to_markdown_file` → `data/raw/web_snapshots/`；`firecrawl_configured()`。           |
| `tools/file_tool.py`                   | `read_file_content`（根内 MarkItDown、根外 `parse_path`）；`ingest_file_to_kb`（盘外 `copy_file=True`）；统一 `format_*_response`。 |
| `tools/response_format.py`             | `schema_version: topic4.tool.v1` 外壳，Firecrawl / 文件工具共用。                                                                           |
| `deep_planning/tools_factory.py`       | `_build_firecrawl_tools`、`_build_c4_file_tools`；移除 `topic4_kb_ingest`、`topic4_file_to_markdown`、`topic4_read_local_file`。    |
| `deep_planning/session_planner.py`     | L1 字段 `needs_web_tools`、`web_urls`、`local_paths`；`format_c4_parsed_input_block` 注入 L2（链接 → scrape，路径 → file_read）。   |
| `deep_planning/agent_runner.py`        | L2 系统提示改为 `topic4_file_read` / `topic4_file_ingest` 与 Firecrawl 分工说明。                                                         |
| `runtime/tools/governance.py`          | C4 工具白名单同步为新名称。                                                                                                                   |
| `orchestration/planning_extensions.py` | 入库提示改为 `topic4_file_ingest`（盘外可复制入库）。                                                                                       |
| `config.py` / `.env.example`         | `FIRECRAWL_API_KEY`、`FIRECRAWL_MAX_OUTPUT_CHARS`、`FIRECRAWL_SEARCH_LIMIT`。                                                           |
| `pyproject.toml`                       | `agent` 依赖组增加 `firecrawl-py`。                                                                                                       |
| `cli/c34_client.py`                    | 状态栏提示：无 Key 时仍可用 `topic4_file_*`。                                                                                               |
| 删除                                     | `tools/local_file_tool.py`（逻辑并入 `file_tool.py`）。                                                                                   |

### C3 / C4 工具对照（客户端 B 线，2026-05-18 起）

| 能力          | C3                   | C4                                   |
| ------------- | -------------------- | ------------------------------------ |
| Chroma 检索   | `topic4_rag_query` | 同左                                 |
| 读本地文件    | ❌                   | `topic4_file_read`（动态）         |
| 本地文件入库  | ❌                   | `topic4_file_ingest`（含盘外复制） |
| 抓网页 / 搜索 | ❌                   | Firecrawl 三件套（需 Key）           |
| 沙箱 Python   | ❌                   | 可选 `sandbox_exec_python`         |

### 典型命令与配置

```powershell
uv sync --group agent
# .env 中配置 FIRECRAWL_API_KEY 后 C4 才出现 firecrawl_* 工具
uv run python main.py client --c4
uv run python main.py agent --c4

# 单测（mock，不调外网）
uv run pytest tests/test_firecrawl_tool.py tests/test_file_tool.py -q
```

### 分工备忘（避免 Agent 误用）

- **Firecrawl 不能读本地磁盘**；**MarkItDown 不抓 http(s)**。
- 用户消息中的 **URL** → 优先 `topic4_firecrawl_scrape`；**本地路径** → `topic4_file_read`；要进 Chroma → `topic4_file_ingest` 或 `topic4_firecrawl_scrape_to_kb`。
- 「开始会话」路径框批量入库逻辑不变；对话内临时路径由 Agent 调 `topic4_file_ingest`。

### 文档同步

- `docs/ARCHITECTURE.md` §2.4、§2.9、§2.10、§5（2026-05-18）
- `docs/agent_runtime_architecture.md` 完成度表（2026-05-18）
- `docs/experiment_stage_and_code_ownership.md` §4.5
- `.cursor/skills/topic4-orchestration-layers/SKILL.md` 工具表

### 本次新增/涉及文件（路径清单）

```text
src/agentic_rag/tools/firecrawl_tool.py
src/agentic_rag/tools/file_tool.py
src/agentic_rag/tools/response_format.py
src/agentic_rag/deep_planning/tools_factory.py
src/agentic_rag/deep_planning/session_planner.py
src/agentic_rag/deep_planning/agent_runner.py
src/agentic_rag/runtime/tools/governance.py
tests/test_firecrawl_tool.py
tests/test_file_tool.py
```

### 仍建议后续改进

- Gradio **对话内附件上传**、**规划前改写** UI 开关。
- `topic4_kb_ingest` 旧名在实验笔记历史段落中仍会出现；代码侧已统一为 `topic4_file_ingest`。
- 编排层 `tool_start`/`tool_end` 事件与审计 JSONL 对齐。

### Git 痕迹

- **截至文档整理时**：本节功能在本地工作区，**尚未单独 commit**；建议在合并后使用类似
  `feat(tools): C4 Firecrawl 与 topic4_file_read/ingest 对称工具族` 提交，并与 `547f8ae`（05-17）区分。

---

## 2026-05-19 系统知识库 sync 与会话临时索引

### 目标

- **`data/raw` 系统子目录**（排除 `session_upload` / `user_docs`）由 `main.py kb sync` 自动写入 `documents.csv` 并重建 Chroma。
- **`main.py kb reset`**：清空 Chroma + `chunks.jsonl` 后全量 sync（干净重启）。
- **客户端附加路径**：仅本会话**临时切块索引**，不写全库；审计事件 `session_scope_ready` / `kb_reset_*`。

### 命令

```powershell
uv run python main.py kb reset
uv run python main.py kb sync
uv run python main.py kb clear-chroma
uv run python main.py client --console --c4 --sync-kb
```

说明见 **`data/raw/README.md`**。

### 涉及模块

`experiment/kb_paths.py`、`kb_sync.py`、`kb_chroma_admin.py`、`documents/session_index.py`、`experiment/session_rag.py`；`multi_doc.py`、`c34_client.py`、`tools_factory.py`、`cli/app.py`。

---

## 当前待办

优先级从高到低：

1. 检查 `c0_results.csv` 和 `c1_results.csv` 中每题答案，人工标注 Answer Correctness 和 Citation 是否真正支撑答案。
2. 补全 `references.csv` 中的 `evidence_chunk_id`，至少先补 20 题的 gold chunk。
3. 整理 Q005、Q007、Q013 三个典型案例：说明 C1 成功/失败的原因。
4. 建立或补充 `docs/evaluation_plan.md`，明确 Recall@5、Answer Correctness、Citation Accuracy、Latency、Token Usage 的判定规则。
5. 基于2026-05-06 的 C2 三阶段消融结果，整理阶段 1→2→3 的成本与检索命中对比，并补齐 **Q013** 等失败案例分析。
6. 后续 C2 扩展实验也必须使用同一知识库、同一测试集，不能换题后再比较。
7. Topic4 Agent：`--once-file` 大批量场景下若要进一步优化体验，评估接入 **流式输出 / 进度回调**；按需收紧第三层研判 Prompt 或结构化输出字段（减少冗长 `need_user_input` 式总结触发重复执行的语义噪声）。
8. **C3/C4 客户端**：2026-05-18 已接 C4 动态 Firecrawl / `topic4_file_*`；仍缺 Gradio 附件上传、规划前改写 UI；见 `experiment_notes` 2026-05-17 / 2026-05-18。

---

## 2026-05-13 C2 正式复现实验与日志修复

记录人：赵启行

阶段：C2 Advanced RAG 正式复现实验验收。

### 一、背景

此前 C2 三阶段实验已经能生成 CSV 结果，但 `runs/logs/c2_*` 下的 `run_logs.jsonl` 为空。排查后确认，问题不是 C2 没有运行，而是日志写入路径设计不正确：

- C2 调用底层 `run_c1_with_index()` 时传入的是总日志目录 `runs/logs`。
- 底层日志函数会根据当时的 `config` 字段写入日志，而当时 `config` 仍是 `c1_rewrite`。
- C2 后续才把 `config` 改成 `c2_stage1_c1_hybrid` 等阶段名。
- 因此 C2 专属日志目录被初始化清空，但实际逐题日志没有写到 C2 目录。

### 二、修复内容

本次修复采用最小改动，不改变 C2 检索、重排、上下文补全主逻辑。

修复方式：

1. C2 调用底层 C0/C1 管线时，先不让底层立即写日志。
2. C2 在拿到结果后，将 `config` 改为当前 C2 阶段名。
3. C2 再调用统一日志工具写入 `runs/logs/<c2_stage>/run_logs.jsonl`。
4. CSV 中的 `log_path` 字段同步指向 C2 专属日志文件。

涉及文件：

```text
run_c2_retrieval_ablation.py
tests/test_c2_logging.py
```

同时修复两个非 C2 的 lint 问题：

```text
src/agentic_rag/deep_planning/agent_runner.py
src/agentic_rag/orchestration/loop.py
```

### 三、验证结果

基础检查：

```text
uv run ruff check .
结果：All checks passed

uv run pytest
结果：24 passed
```

新增测试：

```text
tests/test_c2_logging.py
```

该测试验证：

- C2 阶段日志写入 `runs/logs/<c2_stage>/run_logs.jsonl`。
- 日志记录中的 `config` 是 C2 阶段名，而不是 `c1_rewrite`。
- CSV 行中的 `log_path` 指向 C2 专属日志。

### 四、C2 正式复现实验参数

正式运行命令：

```powershell
uv run python run_c2_retrieval_ablation.py --phase all --limit 20 --neighbors 1
```

固定参数：

```text
phase=all
limit=20
use_query_rewrite=true
top_k=5
rerank_pool_size=20
rerank_backend=llm
dense_weight=0.6
bm25_weight=0.4
neighbors_stage3=1
index_cache=enabled
force_rebuild=false
```

说明：

- 本次使用同一知识库、同一 20 条核心测试题、同一 C1 query rewrite 基础。
- 使用本地 embedding cache，未强制重建索引。
- 中途曾出现网络 `Connection error`，错误轮次已备份到本地 `archive/`，不作为正式结果。
- 网络恢复后重新完整运行 C2 三阶段，并完成日志修复后的正式复现。

### 五、C2 正式复现实验结果

| 阶段                                   | 题数 | 错误 | 文档级命中 | Gold chunk 命中 | 平均延迟(ms) | 平均 token | 平均检索 query 数 |
| -------------------------------------- | ---: | ---: | ---------: | --------------: | -----------: | ---------: | ----------------: |
| `c2_stage1_c1_hybrid`                |   20 |    0 |      19/20 |            9/20 |        17719 |       2143 |              4.00 |
| `c2_stage2_c1_hybrid_rerank`         |   20 |    0 |      20/20 |           15/20 |        28761 |      12462 |              3.85 |
| `c2_stage3_c1_hybrid_rerank_context` |   20 |    0 |      20/20 |           15/20 |        27887 |      14462 |              4.15 |

日志校验：

| 阶段                                   | CSV 行数 | CSV error | JSONL 日志行数 | 日志 config                            |
| -------------------------------------- | -------: | --------: | -------------: | -------------------------------------- |
| `c2_stage1_c1_hybrid`                |       20 |         0 |             20 | `c2_stage1_c1_hybrid`                |
| `c2_stage2_c1_hybrid_rerank`         |       20 |         0 |             20 | `c2_stage2_c1_hybrid_rerank`         |
| `c2_stage3_c1_hybrid_rerank_context` |       20 |         0 |             20 | `c2_stage3_c1_hybrid_rerank_context` |

输出文件：

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

这些 `runs/` 下的文件属于本地实验输出，默认不提交到 GitHub。

### 六、阶段性解释

1. Stage1 只加入 hybrid retrieval 后，文档级命中为 19/20，Gold chunk 命中为 9/20，说明混合检索能改善召回，但还不能稳定命中精确证据块。
2. Stage2 加入 LLM rerank 后，文档级命中提升到 20/20，Gold chunk 命中提升到 15/20，说明 rerank 对证据排序有明显帮助。
3. Stage3 加入 context expansion 后，文档级命中和 Gold chunk 命中没有继续提升，平均 token 进一步增加，因此不能仅凭检索指标证明上下文补全有效。
4. C2 的正式结论不能只看文档命中率，还必须补充人工 `Answer Correctness` 和 `Citation Accuracy`。
5. AI Judge 只能作为辅助评测工具，最终结论以人工评分为准。

### 七、下一步

1. 唐宁建立 `data/testset/manual_eval_c2.csv`。
2. 先完成 C2 Stage2 的 20 题人工评分。
3. 再补 Q005、Q007、Q013、Q018 的三阶段横向对比。
4. 赵启行汇总 C0/C1/C2 总表：文档命中、Gold chunk 命中、答案正确率、引用准确率、延迟、token。
5. 李金航解释 C2 三阶段的技术收益、成本变化和失败案例。
6. C2 人工验收完成后，再判断是否阶段性冻结 C2。

---

## 2026-05-18 C2 Stage3 选择性上下文扩展优化与复盘

记录人：赵启行

阶段：C2 Advanced RAG / Stage3 context expansion 优化复盘。

### 一、背景

唐宁补充 `data/testset/manual_eval_c2.csv` 后，C2 三阶段人工评分显示：

| 配置                                           | Answer Correctness | Citation Accuracy | 主要问题                          |
| ---------------------------------------------- | -----------------: | ----------------: | --------------------------------- |
| `c2_stage1_c1_hybrid`                        |              0.600 |             0.625 | 部分答案不完整                    |
| `c2_stage2_c1_hybrid_rerank`                 |              0.800 |             0.800 | 整体最好，仍有少量 partial answer |
| `c2_stage3_c1_hybrid_rerank_context`（旧版） |              0.150 |             0.200 | `unsupported_refusal` 14/20     |

旧版 Stage3 采用固定邻接扩展：对 Top-K 命中块统一拼接 `±1` 邻接 chunk。该策略能增加上下文，但也会引入不相关内容，导致模型在部分题目中错误判断“证据不足”。因此，本次优化目标不是继续扩大上下文，而是将 Stage3 改为“选择性上下文扩展”。

### 二、优化规则

新版 Stage3 采用以下规则：

1. 只对 `multi_doc`、`fuzzy_query`、`insufficient_evidence` 题型启用上下文扩展。
2. 不对 `simple_qa`、`calculation`、`code_execution`、`table_analysis` 题型启用上下文扩展。
3. 只扩展 `rank <= 3` 的命中 chunk。
4. 只扩展同一 `doc_id` 下的相邻 chunk。
5. 遇到新的 Markdown 标题边界时停止向后扩展，避免跨小节引入噪声。
6. 对总上下文字符数设置上限，超过上限时截断或跳过扩展。
7. citation 仍保留原始命中 `chunk_id`，同时在日志中记录 `expanded_chunk_ids`、`context_expansion_applied` 和 `context_expansion_reason`。
8. 如果没有触发扩展，则 Stage3 的输出应尽量接近 Stage2。

涉及代码文件：

```text
src/agentic_rag/rag/context_expand.py
src/agentic_rag/pipelines/local_rag.py
src/agentic_rag/schemas.py
src/agentic_rag/experiment/c2_ablation_metrics.py
run_c2_retrieval_ablation.py
tests/test_rerank_context.py
```

### 三、实验前备份

重跑新版 Stage3 前，旧版 Stage3 输出已备份到：

```text
archive/experiment_runs/c2_stage3_before_selective_context_2026-05-18_211229/
```

备份内容包括：

```text
runs/results/c2_stage3_c1_hybrid_rerank_context_results.csv
runs/logs/c2_stage3_c1_hybrid_rerank_context/run_logs.jsonl
runs/results/c2_ablation_summary.json
runs/results/c2_ablation_report.md
```

说明：`archive/` 属于本地备份目录，默认不提交到 GitHub。

### 四、重跑命令

本次只重跑 Stage3，因为 Stage1 和 Stage2 逻辑未修改：

```powershell
uv run python run_c2_retrieval_ablation.py --phase 3 --limit 20 --neighbors 1
```

运行结果：

```text
题数：20
error_count：0
输出文件：
runs/results/c2_stage3_c1_hybrid_rerank_context_results.csv
runs/logs/c2_stage3_c1_hybrid_rerank_context/run_logs.jsonl
runs/results/c2_ablation_summary.json
runs/results/c2_ablation_report.md
```

运行时脚本自动将旧版 `.kb_embedding_cache.pkl` 迁移到 Chroma 后删除旧 pkl 缓存。这是 C2 脚本的索引缓存迁移行为，不是手动删除实验结果。

### 五、优化前后初步对比

| 配置                        | 文档命中 | Gold chunk 命中 | 平均延迟(ms) | 平均 token | 人工 Answer | 人工 Citation |
| --------------------------- | -------: | --------------: | -----------: | ---------: | ----------: | ------------: |
| Stage2：hybrid + rerank     |    20/20 |           15/20 |        28761 |      12462 |       0.800 |         0.800 |
| 旧 Stage3：固定邻接扩展     |    20/20 |           15/20 |        27887 |      14462 |       0.150 |         0.200 |
| 新 Stage3：选择性上下文扩展 |    19/20 |           15/20 |        37057 |      13352 |  待人工评分 |    待人工评分 |

注意：

- 新 Stage3 的 Gold chunk 命中仍为 15/20，与 Stage2 和旧 Stage3 一致。
- 新 Stage3 的平均 token 为 13352，低于旧 Stage3 的 14462，但仍高于 Stage2。
- 新 Stage3 的文档命中为 19/20，低于 Stage2 和旧 Stage3 的 20/20，需要后续检查未命中的题目。
- 由于答案生成存在模型随机性，新 Stage3 是否真正优于旧 Stage3，必须以新的人工评分为准。

### 六、选择性扩展触发情况

新版 Stage3 的 `context_expansion_applied_count` 显示，扩展只发生在以下题目：

| 题号 | task_type                 | 扩展次数 |
| ---- | ------------------------- | -------: |
| Q005 | `fuzzy_query`           |        3 |
| Q006 | `fuzzy_query`           |        3 |
| Q007 | `fuzzy_query`           |        3 |
| Q008 | `fuzzy_query`           |        3 |
| Q009 | `multi_doc`             |        3 |
| Q010 | `multi_doc`             |        3 |
| Q011 | `multi_doc`             |        3 |
| Q012 | `multi_doc`             |        3 |
| Q020 | `insufficient_evidence` |        3 |

未触发扩展的题型包括：

```text
simple_qa
table_analysis
calculation
code_execution
```

这说明选择性触发规则已经生效：Stage3 不再对所有题目无条件做邻接扩展。

### 七、阶段性判断

本次优化已经解决了工程规则层面的问题：

1. Stage3 不再是无条件固定邻接扩展。
2. 扩展触发与题型边界一致。
3. 日志和 CSV 中可以追踪每题是否扩展、扩展了哪些 chunk、扩展原因是什么。
4. token 成本相比旧 Stage3 有所下降。

但目前还不能冻结“新 Stage3 有效”的结论，原因是：

1. 新 Stage3 尚未进行人工 `Answer Correctness` 和 `Citation Accuracy` 标注。
2. 新 Stage3 的文档命中从 20/20 降到 19/20，需要定位具体退化题。
3. 新 Stage3 的平均延迟高于 Stage2 和旧 Stage3，需要结合实际答案质量判断是否值得。
4. Stage2 目前仍是人工评分最好的 C2 配置，不能因为 Stage3 经过优化就默认优于 Stage2。

### 八、下一步

建议建立新的人工评分文件：

```text
data/testset/manual_eval_c2_stage3_selective.csv
```

字段沿用：

```csv
question_id,config,answer_correctness,citation_accuracy,main_problem,comment,reviewer,status
```

唐宁只需要重新标注新版 Stage3 的 20 题，不需要重标 Stage1 和 Stage2。重点检查：

1. `unsupported_refusal` 是否从旧 Stage3 的 14/20 明显下降。
2. Answer Correctness 是否恢复到接近 Stage2。
3. Citation Accuracy 是否恢复。
4. Q005-Q012、Q020 中选择性扩展是否真的改善答案完整性。
5. 未触发扩展的 simple/calculation/code/table 题是否基本接近 Stage2。
6. 新 Stage3 文档命中下降到 19/20 的原因。

最终报告中建议将 Stage3 结论写为：

> 固定邻接式 context expansion 在当前测试集上表现不稳定，甚至会显著降低答案质量；选择性上下文扩展能够降低无效上下文注入，并提供可追踪的扩展日志，但其是否优于 Stage2 rerank 仍需人工评分确认。当前最稳的 C2 主结论仍是 rerank 对检索和答案质量提升最明显。

## 2026-05-18 C3 小批量验证实验记录

### 一、实验目的

本轮实验用于验证 C3 Agentic Retrieval RAG 是否已经具备可运行的基础链路。重点不是冻结 C3 指标，而是检查：任务规划是否能触发、是否调用 RAG 检索工具、是否出现多查询或多 pipeline 行为、gold doc / gold chunk 是否能被覆盖，以及当前 C3 的主要缺陷是什么。

测试题来自：

```text
data/testset/questions_c3_candidates.csv
data/testset/references_c3_candidates.csv
```

题号范围为 Q021-Q030，共 10 题。

### 二、运行前状态

实验前检查：

```powershell
git status --short --branch
git log -1 --oneline
uv run python --version
uv run pytest tests/test_deep_planning_presets.py tests/test_session_planner_json.py tests/test_runtime_tools.py tests/test_runtime_state.py
```

记录结果：

```text
当前分支：main...origin/main
当前 commit：80667b5 Add files via upload
Python：3.12.10
C3 相关测试：13 passed
```

运行前本地已有 C2 Stage3 优化相关未提交改动，本轮未处理这些改动，也未推送仓库。

### 三、最小修复

第一次运行 Q021-Q030 时，C3 入口在进入规划前失败：

```text
TypeError: OrchestrationConfig.__init__() got an unexpected keyword argument 'enable_c4_tools'
```

原因是 `main.py agent --c3` 和 C3/C4 客户端已经按 C3/C4 档位设计传入 `enable_c4_tools`，但 `OrchestrationConfig` 中缺少该字段。随后进行了最小修复：

1. 在 `src/agentic_rag/orchestration/types.py` 中为 `OrchestrationConfig` 增加 `enable_c4_tools: bool = False`。
2. 在 `src/agentic_rag/orchestration/loop.py` 中将 `cfg.enable_c4_tools` 传给 `build_topic4_deep_agent(...)`。
3. 在 `compose_layer2_user_message(...)` 中传递 `enable_c4_tools=cfg.enable_c4_tools`，保证 C3 只启用检索工具，C4 才启用外部工具。
4. 将 `--json` 调试输出改为 `ensure_ascii=True`，避免 Windows GBK 控制台在打印特殊字符时触发 `UnicodeEncodeError`。

修复后验证：

```powershell
uv run pytest tests/test_deep_planning_presets.py tests/test_session_planner_json.py tests/test_runtime_tools.py tests/test_runtime_state.py
uv run ruff check src\agentic_rag\orchestration\types.py src\agentic_rag\orchestration\loop.py
```

结果：

```text
13 passed
All checks passed
```

### 四、运行命令

单题运行命令模板：

```powershell
uv run python main.py agent --c3 --planning-rewrite --json --once "<题目文本>"
```

为避免 Windows 控制台编码问题，批量运行时使用：

```powershell
$env:PYTHONIOENCODING="utf-8"
$env:PYTHONUTF8="1"
```

### 五、输出文件

本轮输出：

```text
runs/results/c3_smoke_results.csv
runs/logs/c3_agentic_retrieval/run_logs.jsonl
runs/logs/c3_agentic_retrieval/summary.json
runs/logs/c3_agentic_retrieval/Q021_console.txt
...
runs/logs/c3_agentic_retrieval/Q030_console.txt
```

两轮失败记录已本地备份到：

```text
archive/experiment_runs/c3_smoke_failed_before_config_fix_2026-05-18
archive/experiment_runs/c3_smoke_failed_before_json_encoding_fix_2026-05-18
```

说明：`archive/` 与 `runs/` 默认不提交仓库。

### 六、结果摘要

最终有效结果：

| 指标                      |      结果 |
| ------------------------- | --------: |
| 总题数                    |        10 |
| 程序级错误                |         0 |
| RAG 调用                  |     10/10 |
| 多查询 / 多 pipeline 行为 |     10/10 |
| 平均延迟                  | 152038 ms |
| 平均 gold doc 覆盖率      |    0.9000 |
| 平均 gold chunk 覆盖率    |    0.6067 |

逐题结果：

| 题号 | 类别     | gold doc 覆盖 | gold chunk 覆盖 | 延迟(ms) |
| ---- | -------- | ------------: | --------------: | -------: |
| Q021 | 多轮检索 |           2/3 |             1/3 |   138887 |
| Q022 | 基础验收 |           4/4 |             3/4 |   136057 |
| Q023 | 多轮检索 |           5/5 |             3/5 |   133619 |
| Q024 | 基础验收 |           3/3 |             5/6 |   126346 |
| Q025 | 多轮检索 |           2/3 |             3/6 |   196684 |
| Q026 | 基础验收 |           3/3 |             4/5 |   114438 |
| Q027 | 压力测试 |           2/3 |             1/3 |   178996 |
| Q028 | 基础验收 |           3/3 |             2/4 |   139056 |
| Q029 | 压力测试 |           2/2 |             2/3 |   282236 |
| Q030 | 基础验收 |           1/1 |             3/4 |    74062 |

### 七、阶段判断

C3 当前已经可以跑通，并且能体现 C3 的关键行为：

1. 能走 Agent 编排入口。
2. 能在规划后调用 RAG 工具。
3. 10 题全部出现多查询或多 pipeline 行为。
4. gold doc 覆盖率达到 90%，说明文档级证据召回基本可用。

但 C3 还不能冻结，主要问题是：

1. 平均延迟约 152 秒，成本明显偏高。
2. gold chunk 覆盖率约 60.67%，说明证据精确定位仍不稳定。
3. Q021、Q025、Q027 的证据覆盖偏弱，复杂拆解和模糊查询仍需优化。
4. 当前结果尚未进行人工 `Answer Correctness` 和 `Citation Accuracy` 标注。
5. `c3_smoke_results.csv` 是 smoke test 结果，不等同于正式 C3 批量实验结果。

### 八、下一步

建议唐宁基于以下文件进行人工复核：

```text
runs/results/c3_smoke_results.csv
runs/logs/c3_agentic_retrieval/Q021_console.txt
...
runs/logs/c3_agentic_retrieval/Q030_console.txt
```

建议新增人工评分文件：

```text
data/testset/manual_eval_c3_smoke.csv
```

字段建议：

```csv
question_id,answer_correctness,citation_accuracy,planning_quality,retrieval_sufficiency,main_problem,comment,reviewer,status
```

后续如果人工评分显示 C3 答案质量可接受，再进入正式 C3 批量脚本开发；如果人工评分发现答案质量不稳定，应先优化 planner 子查询拆解、最大调用次数和超时控制。

更详细的 C3 实验复现说明见：

```text
docs/c3_smoke_experiment_guide.md
```

## 2026-05-19 C4 专用工具、C3/C4 批量与 Gradio 流式（工程增补）

记录人：李金航

阶段：C4 工具对齐开题 + C3/C4 可复现批量 + Demo 体验。

对应任务：开题「四类外部工具」、C3 smoke 批量、客户端可观测性；**不要求远端沙箱**（采用本地子进程沙箱）。

### 已完成（代码与文档）

1. **C4 专用工具**（与 `data/testset/questions.csv` 中 `required_tool` 对齐）

   - `src/agentic_rag/tools/calculator_tool.py` → Agent 工具 `topic4_calculator`
   - `src/agentic_rag/tools/table_analyzer_tool.py` → `topic4_table_analyzer`（pandas；兼容带 Markdown 前言的 CSV）
   - `src/agentic_rag/tools/code_runner_tool.py` → `topic4_code_runner`（底层 `sandbox/local_subprocess.py`）
   - 注册于 `deep_planning/tools_factory.py`；C4 且 `SANDBOX_ENABLED=true` 时另保留 `sandbox_exec_python` 兼容名
2. **C3/C4 批量评测**（与 `main.py client` **同一套** `QueryEngine` + 编排链，非旁路脚本）

   - `src/agentic_rag/experiment/c34_batch.py`
   - 根目录 `run_c34_batch_eval.py`；亦可 `uv run python main.py experiment c34 ...`
   - 预设拆分：`c3_smoke`（Q021–Q030）、`c4_tools`（Q013,Q016–Q019）、`main_20`、`ids`
   - 日志：`runs/logs/c3_agentic_retrieval_batch/`、`runs/logs/c4_tool_augmented_batch/`
3. **Gradio 流式展示**

   - `cli/c34_client.py`：`iter_c34_turn_stream`、`_chat_stream`；编排事件经 `telemetry/streaming_hooks.py` 推送
4. **缺陷修复**

   - `orchestration/loop.py`：删除重复的 `enable_c4_tools=` 实参（曾导致 SyntaxError）
5. **单测**

   - `tests/test_c4_computation_tools.py`（5 passed）
6. **文档同步**

   - 根目录 `README.md` §12 进度与打开方式
   - `docs/ARCHITECTURE.md` §5、工具表、C3/C4 流程图
   - 本条目

### 关键命令

```powershell
# 环境
uv sync --group agent
# .env: DEEPSEEK_API_KEY, ARK_API_KEY；C4 代码题建议 SANDBOX_ENABLED=true

# 打开 Demo
uv run python main.py kb sync
uv run python main.py client --c4 --sandbox

# C3 smoke 批量
uv run python run_c34_batch_eval.py --tier c3 --split c3_smoke --verbose-events

# C4 工具向题批量
uv run python run_c34_batch_eval.py --tier c4 --split c4_tools --sandbox

# 单测
uv run pytest tests/test_c4_computation_tools.py -q
```

### 输出文件（批量跑完后）

```text
runs/logs/c3_agentic_retrieval_batch/run_logs.jsonl
runs/logs/c3_agentic_retrieval_batch/batch_report.json
runs/logs/c4_tool_augmented_batch/run_logs.jsonl
runs/logs/c4_tool_augmented_batch/batch_report.json
```

每行 JSONL 含：`question_id`、`events[]`（L1/L2/L3 摘要）、`session_id`、`latency_ms`。

### 设计说明（答辩可用）

| 开题名称       | 实现                      | 说明                                            |
| -------------- | ------------------------- | ----------------------------------------------- |
| file_reader    | `topic4_file_read`      | 根内 MarkItDown，根外 `parse_path`            |
| calculator     | `topic4_calculator`     | AST 安全算术，非 LLM 心算                       |
| table_analyzer | `topic4_table_analyzer` | pandas 统计；**不是** MarkItDown          |
| code_runner    | `topic4_code_runner`    | 本地临时目录子进程；**非** Modal 远端沙箱 |

Deep Agents 参考：[Overview](https://docs.langchain.com/oss/python/deepagents/overview) — 本项目 L2 已用 `create_deep_agent`；内置 `write_todos`/虚拟 FS 由 harness 提供；**执行隔离**采用自研轻量沙箱以满足课程可复现要求。

### 主要结果

- 工具层单测通过；**全量 C3/C4 批量实验与人评尚未在本日跑完**（需组员执行上述命令并填 `manual_eval_*.csv`）。

### 遇到问题

- `rag_eval_results.csv` 含 Markdown 前言，直接 `read_csv` 会失败 → 已在 `table_analyzer` 中跳过前言行。
- Windows 控制台编码可能导致 Agent 输出乱码 → 批量建议 `$env:PYTHONUTF8=1`。

### 下一步

1. 跑满 `c3_smoke` / `c4_tools` 批量并人工抽检。
2. 题集扩至 40–50 题。
3. 补 C4 消融配置与 Benchmark/C5 样例。
4. 整理 10+ 失败案例写入计划中的 `failure_cases.md`。

## 2026-05-19 C4 文件写盘、编辑与受限 shell（工程增补）

记录人：李金航

阶段：C4 工具增强 — 工程内文本写入/局部编辑、PowerShell/sh 命令（非任意主机管理员权限）。

对应任务：开题「文件读取/操作」与演示侧「改 raw 草稿、跑简单命令」；与既有 `topic4_file_read` / `topic4_file_ingest` 互补。

### 已完成

1. **写盘与编辑**（`FILE_WRITE_ENABLED`，默认 true）

   - `topic4_file_write`：覆盖/追加 UTF-8 文本
   - `topic4_file_edit`：search-replace（可 `replace_all`）
   - 底层 `tools/file_tool.py` + `tools/path_policy.py`（禁止 `.env`、`.git/`、`uv.lock`、`documents.csv` 等）
2. **命令执行**（`SHELL_COMMAND_ENABLED`，默认 true）

   - `topic4_shell_exec`：工程子目录或会话沙箱 cwd；Windows 为 PowerShell
   - `sandbox/shell_runner.py`：命令黑名单（`rm -rf`、`pip install` 等）
3. **注册与文档**

   - `tools_factory.py`、`governance.py`、`agent_runner` / `session_planner` 提示词
   - `configs/c4_tool_augmented.yaml`：`allow_file_write: true`
   - `tests/test_file_ops_tools.py`（5 项，与 C4 计算工具测一并 10 passed）

### 环境变量

```text
FILE_WRITE_ENABLED=true
SHELL_COMMAND_ENABLED=true
SHELL_TIMEOUT_SEC=60
SANDBOX_ENABLED=true    # Python 代码题仍建议开启
```

### 使用注意

- 写入 `data/raw/` 后需 **`main.py kb sync`** 或 **`topic4_file_ingest`** 才进 Chroma。
- C3 模式仍无写盘/shell 工具。
- 关闭写盘：`.env` 设 `FILE_WRITE_ENABLED=false`（同时不注册 write/edit）。

## 2026-05-19 C2 Stage3 两轮优化复盘与最终保留版本

记录人：赵启行

阶段：C2 Advanced RAG / Stage3 context expansion 继续优化。

### 一、优化背景

5 月 18 日已将 Stage3 从“固定邻接 chunk 扩展”改为“选择性上下文扩展”。该版本相比最早的固定扩展，已经解决了无条件拼接上下文导致大量 `unsupported_refusal` 的问题，但仍存在两个需要继续补强的点：

1. 日志字段不够清楚，难以区分原始检索证据、扩展上下文和最终引用证据。
2. 扩展 chunk 的筛选规则还需要更可控，避免把无关上下文拼入最终提示词。

因此本轮对 Stage3 做了两次小范围优化，均不改变 Stage1/Stage2 主逻辑。

### 二、第一次优化：补充日志字段与轻量过滤

本次优化目标是让 Stage3 的扩展行为更可追踪，便于后续人工评分和错误归因。

主要改动：

1. 在 Stage3 输出和日志中区分以下字段：
   - `retrieved_chunk_ids`：原始检索和 rerank 后命中的 chunk。
   - `expanded_chunk_ids`：上下文扩展额外加入的 chunk。
   - `final_citation_chunk_ids`：最终答案中实际引用或保留为引用来源的 chunk。
2. 只对需要上下文补全的题型启用扩展，例如 `multi_doc`、`fuzzy_query`、`insufficient_evidence`。
3. 不对 `simple_qa`、`calculation`、`code_execution`、`table_analysis` 等题型启用扩展。
4. 只扩展排名靠前的命中 chunk，且要求扩展 chunk 与命中 chunk 属于同一文档、同一小节。
5. 加入上下文预算限制，超过预算时不继续扩展。

该版本提升了可解释性：后续可以明确判断某道题的答案问题来自“原始检索没命中”，还是“扩展上下文引入噪声”，或者“最终引用选择不准确”。

### 三、第二次优化：尝试 keyword filter 后舍弃

在第一次优化基础上，曾尝试加入关键词过滤，即要求扩展 chunk 包含问题关键词或改写关键词后才允许进入上下文。该策略的初衷是减少无关 chunk，但实验结果显示效果反而下降。

AI Judge 辅助评分结果：

| 配置                     | Answer Correctness | Answer Completeness | Citation Accuracy | Faithfulness | 加权分 |
| ------------------------ | -----------------: | ------------------: | ----------------: | -----------: | -----: |
| Stage2 rerank            |              0.625 |               0.625 |             0.625 |        0.950 |  0.706 |
| Stage3 old selective     |              0.750 |               0.725 |             0.675 |        0.950 |  0.775 |
| Stage3 keyword filter    |              0.600 |               0.600 |             0.600 |        0.900 |  0.675 |
| Stage3 no keyword filter |              0.750 |               0.725 |             0.675 |        0.925 |  0.769 |

运行指标对比：

| 配置                     | 题数 | 文档命中 | Gold chunk 命中 | 触发扩展题数 | 扩展 chunk 总数 | 平均延迟(ms) | 平均 token |
| ------------------------ | ---: | -------: | --------------: | -----------: | --------------: | -----------: | ---------: |
| Stage2 rerank            |   20 |    20/20 |           15/20 |            0 |               0 |        28761 |      12462 |
| Stage3 old selective     |   20 |    19/20 |           15/20 |            9 |              27 |        37057 |      13352 |
| Stage3 keyword filter    |   20 |    20/20 |           15/20 |            9 |              26 |        67001 |      13590 |
| Stage3 no keyword filter |   20 |    19/20 |           15/20 |            9 |              27 |        72406 |      13018 |

阶段判断：

1. `keyword filter` 版本不保留为后续主线版本。
2. 关键词过滤会误伤部分有效上下文，尤其是同一小节中具有补充解释作用、但未直接重复问题关键词的 chunk。
3. `keyword filter` 版本在答案正确性、完整性、引用准确性和 faithfulness 上均低于 `old selective` 与 `no keyword filter`，因此不作为后续 C2 Stage3 结论依据。
4. `no keyword filter` 版本与 `old selective` 在核心质量指标上基本持平，只有 faithfulness 和加权分略低，差异较小，不能判定为显著退化。
5. `no keyword filter` 的平均延迟明显高于 `old selective`，但平均 token 并未增加，暂时更可能与 LLM/API 调用波动有关，后续不应只凭单次延迟判断算法成本。

### 四、最终保留的 Stage3 版本

后续 Stage3 暂时采用以下版本：

```text
选择性上下文扩展 + 清晰日志字段 + 同文档/同小节约束 + 上下文预算限制
```

不保留：

```text
keyword filter 版本
```

保留版本的主要规则：

1. 只在 `multi_doc`、`fuzzy_query`、`insufficient_evidence` 等题型上考虑扩展。
2. 不在简单问答、计算、代码执行、表格分析等题型上扩展。
3. 只扩展排名靠前的命中 chunk。
4. 只扩展同一 `doc_id`、同一小节内的相邻 chunk。
5. 使用上下文预算限制，超过预算则跳过扩展。
6. 日志中必须保留 `retrieved_chunk_ids`、`expanded_chunk_ids`、`final_citation_chunk_ids`。

### 五、当前结论

1. Stage3 固定邻接扩展已经被淘汰，不适合作为正式方案。
2. Stage3 选择性扩展比固定扩展更合理，能够减少无效上下文注入，并提供可追踪日志。
3. keyword filter 版本实测效果较差，后续不再作为主线版本。
4. 当前保留的 no keyword filter 版本在 AI Judge 辅助评分中基本恢复到 old selective 水平，但仍不能证明稳定优于 Stage2。
5. C2 当前最稳的结论仍然是：Stage2 的 hybrid retrieval + rerank 对检索和答案质量提升最明确；Stage3 context expansion 可作为边界分析和失败案例讨论，不宜过度强调为主要增益点。

### 六、后续动作

1. 唐宁后续人工评分时，重点检查 Stage3 no keyword filter 版本中 Q007、Q013、Q014、Q017 等低分题。
2. 人工评分需要区分三类问题：
   - 原始检索未命中。
   - 扩展上下文引入噪声。
   - 最终答案引用不准确。
3. 最终报告中，Stage3 应写成“经过选择性扩展优化后可用性改善，但收益不稳定”，而不是写成“Stage3 明显优于 Stage2”。
4. AI Judge 评分只作为辅助参考，正式结论仍以人工 `Answer Correctness` 和 `Citation Accuracy` 为准。

## 2026-05-24 C3 30 题完整版批量实验记录

记录人：赵启行

阶段：C3 Agentic Retrieval RAG 正式批量验证。

本轮按“C3 完整版”运行 Q001-Q030 共 30 题，目标是验证当前 C3 是否能稳定体现任务规划、查询拆解、多次 RAG 检索、多 pipeline 选择、初步答案整合与证据检查能力。本轮开启 `planning-rewrite`，因此后续结论应写作“C3 完整版 + planning-rewrite”，不能把全部效果单独归因于 planning。

### 一、实验配置

```text
commit = 31434a6 docs: reorganize readme and repository documentation
python = 3.12.10
tier = c3
split = ids
question_ids = Q001-Q030
planning_rewrite_enabled = true
max_orchestration_rounds = 默认值
max_execute_retries_per_round = 默认值
```

知识库状态：

```text
实验前已执行：uv run python main.py kb sync
知识库文件：data/processed/chunks.jsonl
chunks.jsonl SHA256 = 9D2913CBD42669BCA2A00CCFF0843DEFA822350F72D533CA4CBA2DA3A365A4D1
索引方式：自实现轻量内存向量索引 SimpleVectorIndex
embedding 缓存：data/processed/kb_embedding_cache.pkl
说明：本轮 C3 不是基于 Chroma 向量数据库运行。
```

正式运行命令：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$ids = (1..30 | ForEach-Object { 'Q{0:D3}' -f $_ }) -join ','
uv run python run_c34_batch_eval.py `
  --tier c3 `
  --split ids `
  --question-ids $ids `
  --planning-rewrite `
  --log-dir runs/logs/c3_agentic_retrieval_30_batch_full_20260524
```

### 二、输出文件

```text
runs/results/c3_ids_results.csv
runs/results/c3_formal_30_llm_judged.csv
runs/results/c3_formal_30_questions.csv
runs/results/c3_formal_30_references.csv
runs/logs/c3_agentic_retrieval_30_batch_full_20260524/run_logs.jsonl
runs/logs/c3_agentic_retrieval_30_batch_full_20260524/batch_report.json
docs/c3_formal_30_experiment_report.md
```

其中 `docs/c3_formal_30_experiment_report.md` 已覆盖为 C3 完整版实验报告。

### 三、实验结果摘要

| 指标 | 结果 |
| --- | ---: |
| 题目数 | 30 |
| 成功完成 | 30 |
| 程序级错误 | 0 |
| 总运行耗时 | 约 78.4 分钟 |
| 平均延迟 | 156693.3 ms |
| p95 延迟 | 480413 ms |
| 平均 RAG 调用次数 | 10.8667 |
| 多次检索题数 | 22/30 |
| 平均 gold doc coverage | 0.9228 |
| 平均 gold chunk coverage | 0.6975 |
| AI Judge Answer Correctness | 0.7667 |
| AI Judge Answer Completeness | 0.7667 |
| AI Judge Citation Accuracy | 0.7500 |
| AI Judge Faithfulness | 0.9500 |
| AI Judge 加权综合分 | 0.8083 |

按题目来源分组：

| 分组 | 题数 | 平均延迟(ms) | 平均 RAG 调用 | gold doc coverage | gold chunk coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| Q001-Q020 主测试集 | 20 | 138348.75 | 8.95 | 0.9008 | 0.6246 |
| Q021-Q030 C3 候选题 | 10 | 193382.4 | 14.7 | 0.9667 | 0.8433 |

按任务类型分组：

| 任务类型 | 题数 | 平均延迟(ms) | 平均 RAG 调用 | gold doc coverage | gold chunk coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| simple_qa | 4 | 65450.50 | 3.75 | 1.0000 | 0.3458 |
| fuzzy_query | 5 | 127184.60 | 7.40 | 0.7033 | 0.6038 |
| multi_doc | 12 | 201151.00 | 15.50 | 1.0000 | 0.8478 |
| table_analysis | 3 | 326850.67 | 20.67 | 0.9444 | 0.4500 |
| calculation | 2 | 24444.50 | 1.00 | 1.0000 | 1.0000 |
| code_execution | 2 | 36466.50 | 1.50 | 1.0000 | 0.8334 |
| insufficient_evidence | 2 | 143444.00 | 10.50 | 0.6666 | 0.6666 |

观察：

1. `multi_doc` 任务最能体现 C3 的价值，gold doc coverage 达到 1.0000，gold chunk coverage 达到 0.8478，但平均延迟约 201 秒。
2. `simple_qa` 任务不适合全部走完整 C3，doc 级覆盖为 1.0000，但 chunk 级覆盖只有 0.3458，说明多轮检索没有带来稳定收益。
3. `table_analysis` 平均 RAG 调用次数最高，延迟最高，但 chunk 级覆盖只有 0.4500，说明这类任务应交给 C4 表格工具，而不是继续依赖 C3 检索。
4. `calculation` 和 `code_execution` 在本轮覆盖较好，但其本质仍更适合 C4 工具验证。
5. `insufficient_evidence` 任务仍不稳定，需要后续增强证据不足判定与保守回答策略。

### 四、主要问题

覆盖不足或评分偏低的重点题：

```text
Q001, Q002, Q004, Q007, Q008, Q009, Q012, Q013, Q014, Q017, Q020, Q023, Q027
```

其中：

1. Q007、Q008、Q027 说明 fuzzy query / 模糊需求定位仍不稳，planning-rewrite 不能完全解决模糊意图识别。
2. Q013 是典型表格分析任务，C3 多次检索仍难以完成，应进入 C4 工具调用验证。
3. Q009、Q012 的 AI Judge 低分，说明完整 C3 多轮检索可能导致答案偏题或证据组织发散。
4. Q001、Q002、Q004 简单题文档命中但 chunk 定位差，说明 C3 不适合所有问题都走完整链路。
5. Q020 需要人工重点复核：它涉及综合判断，自动覆盖率和最终答案质量不一定一致。

AI Judge 低分题：

```text
Q007, Q008, Q009, Q012, Q013, Q014, Q017, Q023
```

### 五、阶段性结论

1. C3 完整版可以稳定跑完 30 题，程序级错误为 0。
2. 完整版能充分体现 Agentic Retrieval 行为，平均每题 RAG 调用 10.8667 次，22/30 题出现多次检索。
3. C3 对多文档复杂任务更有价值，尤其是 Q021-Q030 候选题的 gold chunk coverage 达到 0.8433。
4. C3 的成本明显升高，平均延迟约 157 秒，p95 延迟约 480 秒，不适合作为所有问题的默认路径。
5. 更多检索不等于更好答案。AI Judge 加权综合分为 0.8083，说明 C3 虽然能覆盖更多证据，但仍可能出现答案发散、偏题或引用不精确。
6. C3 更适合多文档、复杂证据整合和需要多次检索的问题，不适合简单问答、表格分析、计算和代码执行类任务。
7. 本轮仍开启 planning-rewrite，因此报告应写作“C3 完整版 + planning-rewrite”。
8. 若要证明 C3 相比 C2 的收益，仍需后续补 C2 同题对照。

### 六、后续动作

1. 唐宁根据 `runs/results/c3_ids_results.csv` 和 `runs/results/c3_formal_30_llm_judged.csv` 建立人工评分：

```text
data/testset/manual_eval_c3_formal.csv
```

人工评分字段建议包含：

```text
question_id,answer_correctness,citation_accuracy,planning_quality,
multi_round_quality,retrieval_sufficiency,self_check_quality,
main_problem,comment,reviewer,status
```

2. 人工优先复盘：

```text
Q007, Q008, Q009, Q012, Q013, Q020, Q023, Q027, Q029
```

3. 赵启行后续整理 C3 结论时，应强调：
   - C3 完整版能提升复杂多文档任务的证据覆盖；
   - C3 完整版成本高，不适合所有任务；
   - 当前不能直接写成“C3 显著优于 C2”；
   - 需要补 C2 同题对照后，才能做 C2/C3 的正式横向结论；
   - 工具型任务应进入 C4。

4. 李金航后续进入 C4 时，优先用 Q013、Q016-Q019 验证工具调用能否弥补 C3 在表格、计算和代码执行任务上的局限。

## 2026-05-25 C3 主测试集 main_20 正式评测（编排 + LLM Judge）

记录人：李金航

阶段：C3 Agentic Retrieval — 主测试集 `questions.csv`（Q001–Q020）正式批量与答案质量评测。

对应任务：在修复子 Agent 闭包、ToolMessage 兼容、GBK 控制台与编排配额重置后，完整复跑 C3 main_20，形成可复现正式记录与 LLM 辅助判分。

### run_id 与配置

```text
run_id：c3_main_20_formal_20260525
config：C3（enable_c4_tools=false，use_rag_subagent_tools=true）
测试集版本：data/testset/questions.csv（main_20，20 题）
知识库版本：documents.csv sha256 c5273ca1…；chunks.jsonl sha256 90ab25d9…（见 batch_report.run_environment）
Prompt 版本：默认 Topic4 编排 + 子 Agent 提示（planning_rewrite=false）
模型：DeepSeek + Ark embedding（与 batch 运行时 .env 一致）
git：eba24c0（工作区有未提交修复，含 tool_invoke_compat、tool_quota、streaming_hooks 等）
```

### 运行命令

```powershell
cd E:\Agentic-RAG-Evaluation-1
$env:PYTHONIOENCODING = 'utf-8'
uv run python run_c34_batch_eval.py --tier c3 --split main_20
uv run python run_score_rag_multidim.py --results runs/results/c3_main_20_results.csv --out runs/results/c3_main_20_llm_judged.csv
```

正式跑前将旧 `run_logs.jsonl` 备份为 `run_logs_pre_formal_20260525_213754.jsonl.bak`，清空后仅保留本轮 20 行，避免与历史失败 run 混杂。

### 输入数据

```text
data/testset/questions.csv
data/testset/references.csv
工程 Chroma 全库（与 main.py kb sync 口径一致）
```

### 输出文件

| 路径 | 说明 |
|------|------|
| `runs/results/c3_main_20_results.csv` | 正式结果表（答案、引用、gold 覆盖、rag 统计） |
| `runs/results/c3_main_20_llm_judged.csv` | LLM 四维 + weighted 判分 |
| `runs/logs/c3_agentic_retrieval_batch/batch_report.json` | 完整 JSON（含 events、run_environment） |
| `runs/logs/c3_agentic_retrieval_batch/run_logs.jsonl` | 本轮 20 行 JSONL |
| `runs/logs/c3_agentic_retrieval_batch/FORMAL_main_20_2026-05-25.md` | 正式记录摘要（本批） |
| `runs/logs/c3_agentic_retrieval_batch/formal_main_20_console.log` | 终端输出 |
| `runs/logs/audit/sessions/<session_id>/trace.jsonl` | 每题 audit |

### 主要结果（编排层）

| 指标 | 值 |
|------|-----|
| 成功 ok | **20/20（100%）** |
| stop_reason | 均为 complete |
| 总耗时 | 约 **42 分钟** |
| gold_doc_coverage 均值 | **85.9%** |
| gold_chunk_coverage 均值 | **52.0%** |
| doc 覆盖 &lt; 50% | Q007、Q016、Q020 |

耗时 Top5：Q013（717s，58 次 rag）、Q014（648s，44 次）、Q008（182s）、Q012（165s）、Q010（137s）。

### 主要结果（LLM 多维 Judge，辅助，非人工终评）

| 指标 | 值 |
|------|-----|
| `llm_judge_weighted_score` 均值 | **0.850** |
| 中位数 | **0.938** |
| weighted ≥ 0.875 | **16/20** |
| weighted &lt; 0.625 | **2/20**（Q007、Q016） |

薄弱题摘要：

- **Q007**（0.25，wrong_answer）：推荐 LangChain/LlamaIndex/Ragas 等，未对齐参考答案要求的 Dify、RAGFlow、CrewAI、LangGraph。
- **Q016**（0.25，over_refusal）：`rag_eval_results.csv` 未入库，第一层 `needs_retrieval_tools=false`，未计算指标差异。
- **Q013**（0.625，incomplete_answer）：论文类型归纳为 3 类，与参考答案 4 类不完全一致。
- **Q017**（0.625，incomplete_answer）：仅列出 API、Fetcher，缺第三种获取方式（如 urllib 直链）。

**口径**：`ok=20/20` 只表示三层编排无程序异常；答案质量以 Judge / 人工评分为准。

### 与修复前 batch 对比（同 split main_20）

| 问题 | 修复前 | 本轮 |
|------|--------|------|
| GBK 控制台 emoji | 20 题 0ms 失败 | 无 |
| 工具包装闭包 | 子 Agent 实际走 project_default | audit 中 c0/c1/c2 pipeline 正确 |
| LangGraph `unexpected type: str` | Q008–Q015 等失败 | 无 |
| 编排成功率 | 14/20 | **20/20** |

相关修复：`tool_invoke_compat.py`、`tool_quota.py`、`tool_audit.py` 闭包绑定、`orchestration/loop.py` 配额重置；单测 `tests/test_rag_subagent_tools.py`。

### 遇到问题

1. **Q016**：评测 CSV 不在 Chroma，C3 无本地读表工具，只能拒答或要求用户粘贴。
2. **Q007**：多轮检索仍偏向 LangChain/LlamaIndex 文档，gold doc 覆盖仅 25%。
3. **Q013/Q014**：表格归纳题 rag 调用与延迟极高（40–58 次），成本需写入失败/边界案例。
4. **工作区未提交**：正式 run 的 git 状态为 dirty，复现需对齐当日修复文件。

### 失败类型（答案层，非程序失败）

```text
wrong_answer：Q007
over_refusal：Q016
incomplete_answer：Q013、Q017
```

### 下一步

1. 将 `rag_eval_results.csv` 入库或启用 C4 `topic4_table_analyzer`，复测 Q016、Q019。
2. 唐宁按 `manual_eval_c3_formal.csv` 对 Q001–Q020 做人工复核（可与本轮 LLM judge 对照）。
3. 赵启行汇总时区分「编排成功率」与「答案正确率」，勿将 20/20 ok 等同于答案全对。
4. 李金航后续跑 C4 `--split c4_tools` 或 `main_20`，验证工具能否弥补 Q013/Q016/Q017。
5. 可选：对 Q013/Q014 收紧 `max_rag_tool_calls_per_round` 或编排轮次，做延迟消融。

详细逐题表见：`runs/logs/c3_agentic_retrieval_batch/FORMAL_main_20_2026-05-25.md`。
## 2026-05-27：C2 Stage3 回退与 C3-lite-next 30 题实验结论

### 1. 本次操作

本轮完成三件事：

1. 对当前 C2 Stage3 next 结果进行本地备份，备份目录为：
   `archive/experiment_runs/c2_stage3_next_before_rollback_2026-05-27/`
2. 将 C2 Stage3 代码口径回退为旧版 Stage3：
   `C2 Stage2 + context_neighbor_chunks=1`，不再给 `c2_stage3_context` 启用 Evidence Grader。
3. 整理 C3-lite-next 30 题实验结果，并新增完整报告：
   `docs/c3_lite_next_30_experiment_report.md`

### 2. C2 Stage3 结论口径

当前 C2 Stage3 next 在 30 题上的 AI Judge 综合分为 `0.658`，低于旧版 C2 Stage3 的 `0.725`，也低于 C2 Stage2 的 `0.738`。

因此本课题后续采用以下口径：

- C2 主基线：`C2 Stage2 Hybrid + Rerank`。
- C2 Stage3 old：作为上下文扩展边界对照。
- C2 Stage3 next：作为失败优化尝试记录，不作为正式增强方案。

代码上已回退 `c2_stage3_context` 的 preset，使其不再使用 Evidence Grader；Evidence Grader、RRF 和多查询能力仍保留给 C3-lite 使用。

### 3. C3-lite-next 30 题结果

本轮 C3-lite-next 使用以下口径：

```text
--planning-rewrite
--no-adaptive-route
--c3-conservative-opt
```

30 题结果摘要：

| 配置 | 成功题数 | 平均延迟 | 平均 RAG 次数 | Answer Correctness | Citation Accuracy | Faithfulness | 综合分 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C3 formal old | 30/30 | 156.7s | 10.87 | 0.767 | 0.750 | 0.950 | 0.808 |
| C3 conservative old | 30/30 | 98.3s | 5.37 | 0.733 | 0.767 | 0.917 | 0.792 |
| C3-lite-next | 30/30 | 41.6s | 1.60 | 0.750 | 0.717 | 0.967 | 0.796 |

阶段性判断：

- C3-lite-next 相比旧版 C3 conservative 大幅降低延迟和 RAG 调用次数。
- 综合分基本保持，甚至从 `0.792` 小幅提升到 `0.796`。
- 当前 C3 的主要收益集中在 multi_doc、fuzzy_query、insufficient_evidence 任务。
- simple_qa、calculation、code_execution 类题目中，C2 通常已经足够，C3 不应作为所有题的默认路径。

### 4. 后续需要人工复核的题

AI Judge 只能作为辅助。以下题目需要唐宁人工复核：

```text
Q005, Q006, Q012, Q015, Q023, Q027
```

复核重点：

- 是否漏掉 required items；
- claim 与 citation 是否一一对应；
- 是否混淆分类体系；
- 是否出现过度保守或证据不足仍下结论；
- C3 的额外延迟是否换来了真实答案质量收益。
