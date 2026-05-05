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
- `main.py`
- `demo.py`
- `rag_demo.py`
- `upload_demo.py`
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
- 新增 `c1_rewrite_demo.py`，用于单文档 C1 技术演示。
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
uv run python c1_rewrite_demo.py "data/raw/learning_docs/python_basic_sample.md" "切片咋取中间几个元素？"
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
uv run python c1_rewrite_demo.py "data/raw/learning_docs/python_basic_sample.md" "切片咋取中间几个元素？"
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

## 当前待办

优先级从高到低：

1. 配置本地 `.env`，确认 `ARK_API_KEY` 和 `DEEPSEEK_API_KEY` 可用。
2. 用 `python_basic_sample.md` 跑一次真实 C0 和 C1。
3. 收集 3-5 份正式知识库资料。
4. 编写批量 ingest 脚本，生成 `documents.csv` 和 `chunks.jsonl`。
5. 准备首批 20 条测试题和参考证据。
6. 跑 C0 vs C1 小规模对比，记录成功案例和失败案例。
7. C1 稳定后开始 C2：BM25、hybrid retrieval、rerank。
