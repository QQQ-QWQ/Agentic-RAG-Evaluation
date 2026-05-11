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

| 配置 | 日志行数 | 结果行数 | 错误数 | 预期文档命中 | 平均延迟 | 平均 token |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| C0 Naive RAG | 20 | 20 | 0 | 17/20 | 7441 ms | 915 |
| C1 Query Rewrite RAG | 20 | 20 | 0 | 18/20 | 11073 ms | 1328 |

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

| 配置 | 文档级命中 | 未命中题目 | 平均延迟 | 平均 token | 平均检索 query 数 |
| --- | ---: | --- | ---: | ---: | ---: |
| C0 | 17/20 | Q005、Q007、Q013 | 7382 ms | 962 | 1.00 |
| 旧 C1 | 18/20 | Q005、Q013 | 11073 ms | 1329 | 1.75 |
| C1-final | 19/20 | Q013 | 37060 ms | 1905 | 3.95 |

按任务类型统计：

| 任务类型 | C0 | C1-final | 观察 |
| --- | ---: | ---: | --- |
| simple_qa | 4/4 | 4/4 | 清晰事实题中 C1 没有明显额外收益。 |
| fuzzy_query | 2/4 | 4/4 | C1-final 的主要收益来自模糊/口语化问题。 |
| multi_doc | 4/4 | 4/4 | 本轮多文档题 C0 已能命中，C1 提升不明显。 |
| table_analysis | 2/3 | 2/3 | Q013 仍失败，说明仅 query rewrite 不足以解决表格/文件定位干扰。 |
| calculation | 2/2 | 2/2 | 计算题当前仍按文本检索处理，不代表 C4 工具能力。 |
| code_execution | 2/2 | 2/2 | 代码题当前仍按文本检索处理，不代表 C4 工具能力。 |
| insufficient_evidence | 1/1 | 1/1 | 当前样例可命中相关材料，但仍需人工判断答案是否保守。 |

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

| 阶段 key | 题数 | 错误 | 文档级命中 | 命中率 | 均延迟 (ms) | 均 total_tokens | 均检索 query 数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `c2_stage1_c1_hybrid` | 20 | 0 | 20/20 | 100.0% | 10715 | 2130 | 3.90 |
| `c2_stage2_c1_hybrid_rerank` | 20 | 0 | 20/20 | 100.0% | 16130 | 13085 | 4.10 |
| `c2_stage3_c1_hybrid_rerank_context` | 20 | 0 | 19/20 | 95.0% | 13975 | 13536 | 3.85 |

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

| 阶段 | 文档级命中 | 未命中题 | 满分(1.0) | 部分对(0.5) | 错误(0) | 平均得分 | 均延迟(ms) | 均 total_tokens | 均检索 query 数 | 评判消耗 token |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 阶段1：C1+混合检索 | 20/20 | — | 5 | 9 | 6 | 0.475 | 10715 | 2130 | 3.90 | 14385 |
| 阶段2：C1+混合+重排 | 20/20 | — | 9 | 7 | 4 | 0.625 | 16130 | 13085 | 4.10 | 14790 |
| 阶段3：C1+混合+重排+上下文 | 19/20 | Q013 | 1 | 1 | 18 | 0.075 | 13975 | 13536 | 3.85 | 11820 |

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

| 模块 | 内容 |
|------|------|
| `orchestration/*`、`deep_planning/agent_cli.py`、`deep_planning/agent_runner.py`（等与编排入口直接相关的部分） | **本次重写/新增**：调度循环、CLI、`OrchestrationConfig`、与 Deep Agents / LangGraph 的接线方式；**复用**下层 RAG 与工具工厂封装。 |
| `experiment/runner.py` | 新增 `run_knowledge_base_rag`，与 `kb_index_builder.load_or_build_knowledge_index` 共用全库索引。 |
| `experiment/kb_ingest.py` | `ingest_local_file_to_kb`：追加 `documents.csv`、复制至 `data/raw/user_docs/`（默认）、`force_rebuild` 写回 Chroma。 |
| `cli/app.py` | 子命令 `main.py kb ingest …`（`--no-copy` / `--no-rebuild` 等）。 |
| `deep_planning/tools_factory.py` | `topic4_rag_query` 默认全库；绑单文档时用 `run_document_rag`；工具 `topic4_kb_ingest`（路径须在工程根内）。可选 `sandbox_exec_python`（视 `SANDBOX_*`）。 |
| `orchestration/*` | `kb_grounding`、`loop` 中可选对齐核验与研判串联；`OrchestrationConfig` 开关。 |
| `config.py` | `PROJECT_ROOT`；`.env` 优先覆盖 shell 空变量；`DEEPSEEK_API_KEY` 可回退 `OPENAI_API_KEY`。 |
| `orchestration/loop.py` + `agent_cli.py` | 交互默认**多行**：粘贴后以单独一行 `end`/`END` 提交；`--single-line` 恢复单行；`--once-file` / `--stdin` 适合整表 `questions.csv`。 |
| `rag/chroma_store.py` | 对 Chroma 读写加 `RLock`，缓解 LangGraph 并发工具导致的 `Collection … does not exist`。 |
| `session_planner.py` / `agent_runner.py` / `judge_layer.py` | 刷新系统提示词，固化三层 Skill 边界。 |
| `.cursor/skills/topic4-orchestration-layers/SKILL.md` | 编排三层职能说明，供后续改提示词或协作对照。 |

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

## 当前待办

优先级从高到低：

1. 检查 `c0_results.csv` 和 `c1_results.csv` 中每题答案，人工标注 Answer Correctness 和 Citation 是否真正支撑答案。
2. 补全 `references.csv` 中的 `evidence_chunk_id`，至少先补 20 题的 gold chunk。
3. 整理 Q005、Q007、Q013 三个典型案例：说明 C1 成功/失败的原因。
4. 建立或补充 `docs/evaluation_plan.md`，明确 Recall@5、Answer Correctness、Citation Accuracy、Latency、Token Usage 的判定规则。
5. 基于2026-05-06 的 C2 三阶段消融结果，整理阶段 1→2→3 的成本与检索命中对比，并补齐 **Q013** 等失败案例分析。
6. 后续 C2 扩展实验也必须使用同一知识库、同一测试集，不能换题后再比较。
7. Topic4 Agent：`--once-file` 大批量场景下若要进一步优化体验，评估接入 **流式输出 / 进度回调**；按需收紧第三层研判 Prompt 或结构化输出字段（减少冗长 `need_user_input` 式总结触发重复执行的语义噪声）。
