# Topic4 Agentic RAG Evaluation

本项目对应 110 实验室课题四，研究面向学习与知识服务任务的 Agentic RAG 技术增强与评测。

项目当前不是完整产品型学习助手，而是一个逐步搭建的实验工程：通过 C0-C4 对比实验，验证 query rewrite、混合检索、rerank、多轮检索、self-check 和工具调用等模块在 RAG 任务中的作用、成本与边界。

## 当前状态

截至当前版本，项目已完成：

- 项目目录、uv 环境、基础协作规范。
- 从 `Agentic-RAG-110` 迁移并整理 C0 单文档本地 RAG baseline。
- 新增 C1 query rewrite 初版流程。
- 建立 23 条文档记录的初版知识库登记表：`data/processed/documents.csv`。
- 准备 20 条初版测试题：`data/testset/questions.csv` 和 `data/testset/references.csv`。
- 新增 C0/C1 批量实验入口：`run_batch_experiments.py`。
- 已完成一次 C0/C1 20 题批量实验，输出日志和结果表。
- 新增 C0-C4 配置草稿。
- 新增 query rewrite 与 self-check Prompt 初稿。
- 新增 C0-C1 统一接口与日志规范。
- 新增一个最小样例文档用于单文档测试。
- 新增基础测试，当前 `pytest` 通过。
- **检索侧进阶（可视为 C2 管线的一部分）**：在粗检之后可选 **重排（rerank）**，以及在生成前对命中文本做 **上下文邻块扩展（context neighbors）**。
  - 实现位置：`src/agentic_rag/rag/rerank.py`（`none` / `llm`）、`src/agentic_rag/rag/context_expand.py`；编排见 `src/agentic_rag/pipelines/local_rag.py` 中 `retrieve_with_index` → `run_c0_with_index` / `run_c1_with_index`。
  - 运行配置：`RunProfile`（`src/agentic_rag/experiment/profile.py`）与 `experiment/runner.py` 统一传入；默认 **不重排、不扩邻**，避免本地测试误调 API。
  - CLI / YAML：根目录 `main.py rag` 与 `configs/run_default.yaml`（见下文「统一入口」）。

当前尚未完成：

- 持久化向量数据库和正式 `vector_index/`。
- `references.csv` 中的 gold chunk 标注，当前 `evidence_chunk_id` 仍有 `pending`。
- C0/C1 的人工答案质量评分和失败案例分析。
- C2 除 rerank/上下文扩展外的其它约定（若与课题文档有出入，以 `docs/experiment_notes.md` 为准）。
- C3 的任务规划、多轮检索和 self-check 主流程。
- C4 的四类工具调用。
- 公共 Benchmark 子集和 Dify/RAGFlow 横向参考。

## 实验配置

| 配置 | 名称 | 当前定位 |
| --- | --- | --- |
| C0 | Naive RAG | 普通 RAG baseline：文档解析、切块、embedding、Top-K 检索、答案生成。 |
| C1 | Query Rewrite RAG | 在 C0 基础上新增查询诊断与 query rewrite。 |
| C2 | Advanced RAG | 混合检索（稠密 + BM25）已默认启用；**可选 rerank** 与 **邻块上下文扩展** 已接线，其余按课题迭代。 |
| C3 | Agentic Retrieval RAG | 后续新增任务规划、多轮检索和 self-check，不包含外部工具。 |
| C4 | Tool-Augmented Agentic RAG | 后续新增文件读取、代码执行、计算器、表格分析工具。 |

当前代码可运行 C0/C1 的单文档实验雏形；统一入口 ``main.py rag`` 默认接通 Chroma、混合检索与 C1 rewrite，可用 CLI/YAML 关闭任一模块做对照。课题文档中的 C1 边界说明仍以协作共识为准。

当前也可以运行 C0/C1 的同知识库、同测试集批量实验。批量实验中 C0 关闭 query rewrite，C1 只新增 query rewrite；两者都不启用 BM25、hybrid retrieval、rerank、self-check 和工具调用，便于做清晰对照。

## 项目目录

```text
data/       数据、知识库材料、测试集
src/        项目代码
configs/    C0-C4 配置文件草稿
prompts/    Prompt 模板
runs/       实验日志、结果表、图表
docs/       协作规范、接口规范、实验记录
tests/      基础测试
```

重点文档：

- `docs/collaboration_workflow.md`：三人分工、每日同步、每周验收和冲突处理。
- `docs/c0_baseline_architecture.md`：C0 单文档本地 RAG baseline 的代码架构说明。
- `docs/interface_and_logging_rules.md`：C0-C1 输入输出结构、日志字段、验收标准。
- `docs/batch_experiment_guide.md`：C0/C1 批量实验运行说明、输入输出、检查方式和结果解释。
- `docs/directory_rules.md`：目录使用规范。
- `docs/environment_and_git_rules.md`：uv、Python、Git 规范。
- `docs/experiment_notes.md`：实验记录。

## 环境准备

项目统一使用 uv 管理 Python 环境。

```powershell
uv sync
uv run python --version
```

当前本地验证使用 Python 3.12。

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

当前 C0/C1 单文档 RAG 代码实际需要：

```text
ARK_API_KEY
DEEPSEEK_API_KEY
```

流程概述：本地文档解析 → 固定窗口分块 → 火山方舟文本向量 →（可选 **Chroma 持久化**，命中则跳过文档块向量化）→ 内存余弦 Top-K 检索 → DeepSeek 生成回答。

`.env` 不能提交到 GitHub。`.env.example` 只保存变量说明和空示例。

## 运行方式

### 1. 推荐：统一入口 ``main.py``（功能接线、可选开关）

能力集中在根目录 ``main.py``，避免每加一个功能就新建独立 demo。默认：**Chroma + 稠密/BM25 混合检索 + C1 query rewrite**，输出结构化 JSON（含 ``run_profile`` 快照）。

检索阶段顺序（概念上）：**粗检（混合分数排序）→ 可选 rerank（在候选池上精排）→ 可选邻块拼接 → 生成**。重排 **不是** 第二次全库检索，仅在粗检给出的候选池内重排序。

```powershell
# 与默认配置等价（完整链路）
uv run python main.py rag "data/raw/learning_docs/python_basic_sample.md" "切片咋取中间几个元素？"

# 使用 YAML 打底，再用 CLI 覆盖（示例）
uv run python main.py rag "data/raw/learning_docs/python_basic_sample.md" "问题" -c configs/run_default.yaml --log

# 关掉部分模块（示例：纯稠密、走 C0、不用 Chroma）
uv run python main.py rag "...\python_basic_sample.md" "问题" --no-hybrid --no-rewrite --no-chroma

# 启用 LLM 重排（需 DEEPSEEK_API_KEY）；仅用分数截断、不调精排 API 时用：
uv run python main.py rag "...\python_basic_sample.md" "问题" --rerank
uv run python main.py rag "...\python_basic_sample.md" "问题" --rerank --rerank-backend none

# 生成侧上下文：每条命中块向两侧各扩展 N 个相邻切块文本（0 为关闭）
uv run python main.py rag "...\python_basic_sample.md" "问题" --context-neighbors 1
```

**RunProfile / YAML 常用字段**（亦可通过 ``merge_profile_dict`` 扁平传入）：

| 字段 | 含义 |
| --- | --- |
| `use_rerank` | 是否启用检索后重排（默认 `false`） |
| `rerank_backend` | `llm`（DeepSeek 输出候选下标 JSON）或 `none`（按粗检分数截断，不调精排 API） |
| `rerank_pool_size` | 进入重排的粗检候选数量上限（不小于 `top_k`） |
| `context_neighbor_chunks` | 每条命中向左右扩展的切块数（默认 `0`） |

启用 rerank 时，结构化结果里 ``token_usage.rerank`` 会累计精排调用的 token（`backend=none` 时为空对象）。

仅测试 DeepSeek（不经 RAG）：

```powershell
uv run python main.py chat
uv run python main.py chat --prompt "你好"
```

与旧习惯兼容：不加子命令时仍进入「输入一句话」的仅对话交互。

```powershell
uv run python main.py
```

``run_rag.py`` 等价于 ``main.py rag …``，保留仅为兼容。

### 2. 其它脚本（教学或旧入口）

**C0 单文档 RAG Demo**

```powershell
uv run python rag_demo.py "data/raw/learning_docs/python_basic_sample.md" "Python 列表切片怎么取中间几个元素？"
```

也可以使用交互式版本：

```powershell
uv run python demo.py "data/raw/learning_docs/python_basic_sample.md"
```

或 Gradio 上传文档版本：

```powershell
uv run python upload_demo.py
```

### 3. C1 Query Rewrite Demo（与 ``main.py rag`` 等价链路时可替代）

```powershell
uv run python c1_rewrite_demo.py "data/raw/learning_docs/python_basic_sample.md" "切片咋取中间几个元素？"
```

结构化 JSON 字段说明（``main.py rag`` 同样适用），包含：

- `original_query`
- `need_rewrite`
- `rewrite_reason`
- `rewritten_query`
- `retrieval_queries`
- `retrieved_chunks`（若开启邻块扩展，此处文本为扩展后的拼接内容）
- `answer`
- `citations`
- `latency_ms`
- `token_usage`（含 `answer_generation`；C1 另有 `query_rewrite`；启用 rerank 时含 `rerank`）
- `run_profile`（当通过 `run_document_rag` / `main.py rag` 运行时）
- `error`

如果传入 `log_dir`，运行日志会写入：

```text
runs/logs/c1_rewrite/run_logs.jsonl
```

### 4. C0/C1 批量实验

当前推荐用批量脚本做 C0/C1 对照，而不是只看单条 Demo。

运行前先检查代码和测试：

```powershell
uv run ruff check .
uv run pytest
```

运行批量实验：

```powershell
uv run python run_batch_experiments.py
```

输入文件：

```text
data/processed/documents.csv
data/testset/questions.csv
data/testset/references.csv
```

输出文件：

```text
runs/logs/c0_naive/run_logs.jsonl
runs/results/c0_results.csv
runs/logs/c1_rewrite/run_logs.jsonl
runs/results/c1_results.csv
data/processed/chunks.jsonl
```

当前初版批量实验结果：

| 配置 | 题数 | 错误数 | 预期文档命中 | 平均延迟 | 平均 token |
| --- | ---: | ---: | ---: | ---: | ---: |
| C0 Naive RAG | 20 | 0 | 17/20 | 7441 ms | 915 |
| C1 Query Rewrite RAG | 20 | 0 | 18/20 | 11073 ms | 1328 |

详细运行说明见 `docs/batch_experiment_guide.md`。正式结论还需要补齐 gold chunk，并进行人工答案质量和引用可信度评分。

## 当前知识库与样例文档

当前有两类材料：

1. 最小单文档测试材料：

```text
data/raw/learning_docs/python_basic_sample.md
```

它用于验证：

- 文档解析是否正常；
- chunk 切分是否正常；
- C0/C1 单文档链路是否能跑通；
- C1 是否能处理口语化问题。

2. 初版批量实验知识库：

```text
data/processed/documents.csv
data/processed/chunks.jsonl
```

当前 `documents.csv` 记录 23 条材料，`chunks.jsonl` 由批量脚本生成，共 475 个 chunk。它已经可以支持 C0/C1 小规模对照，但仍需要继续补 gold chunk、人工评分规则和失败案例。

## 测试

运行基础测试：

```powershell
uv run pytest
```

运行代码检查：

```powershell
uv run ruff check .
```

运行测试与静态检查后应全部通过（具体数量以本仓库 ``pytest`` / ``ruff`` 输出为准）。

## C1 怎么验收

C1 不是看“能不能改写一句话”，而是看它相对 C0 是否提升了模糊问题的检索和答案质量。

最小验收方式：

1. 准备同一批 15-20 条问题，其中包含清晰问题、模糊问题、口语化问题。
2. 每题标注参考答案和 gold chunk。
3. 用同一知识库分别跑 C0 和 C1。
4. 比较 Recall@5、Answer Correctness、Citation Accuracy、latency 和 token usage。
5. 整理至少 3 个成功案例和 2 个失败案例。

基本验收标准：

- query rewrite JSON 解析成功率为 100%。
- Rewrite Validity 平均分不低于 0.8。
- 模糊问题上 C1 的 Recall@5 高于 C0。
- 清晰问题上 C1 不应明显劣化。
- 日志字段满足 `docs/interface_and_logging_rules.md`。

## 下一步

优先级建议：

1. 补齐 `references.csv` 中的 `evidence_chunk_id`，至少先完成 20 条题的 gold chunk。
2. 人工检查 `c0_results.csv` 和 `c1_results.csv`，标注 Answer Correctness 和 Citation Accuracy。
3. 整理 Q005、Q007、Q013 等成功/失败案例，写清楚 query rewrite 什么时候有帮助、什么时候没帮助。
4. 建立 `docs/evaluation_plan.md`，固定指标定义和评分规则。
5. 在 C0/C1 结果稳定后系统化评测 C2：BM25、hybrid retrieval、rerank、邻块上下文与成本对比。

## 协作提醒

- 不用微信传代码，GitHub 仓库是唯一同步来源。
- 新增依赖使用 `uv add`。
- 不提交 `.env`、`.venv/`、API Key、临时日志和大体积索引。
- 正式实验前冻结测试集、Prompt、配置和模型版本。
- Demo 能跑不等于实验完成，必须有日志、指标和失败案例。
