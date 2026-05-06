# C0/C1 批量实验运行说明

本文档说明如何在当前项目中运行 C0/C1 批量实验，以及如何检查输出是否有效。它面向组内成员使用，重点是保证三个人跑的是同一知识库、同一测试集、同一配置。

## 1. 实验目的

当前批量实验用于回答一个最基础的问题：

> 在同一知识库和同一批测试题上，C1 Query Rewrite RAG 是否比 C0 Naive RAG 有更好的检索和回答效果？

本次实验只比较 C0 和 C1：

| 配置 | 新增能力 | 本次是否启用 |
| --- | --- | --- |
| C0 Naive RAG | 无，作为普通 RAG 基线 | 是 |
| C1 Query Rewrite RAG | query rewrite | 是 |
| C2 Advanced RAG | BM25、hybrid retrieval、rerank | 否 |
| C3 Agentic Retrieval RAG | 任务规划、多轮检索、self-check | 否 |
| C4 Tool-Augmented Agentic RAG | 文件读取、代码执行、计算器、表格分析 | 否 |

因此，C1 相比 C0 的唯一新增变量应该是 query rewrite。不要在 C1 实验里偷偷打开 rerank、工具调用或 self-check，否则后面无法解释提升来自哪里。

## 2. 运行前检查

先确认自己在项目根目录：

```powershell
cd "E:\Agentic RAG\topic4-ARAG-eval"
```

同步环境：

```powershell
uv sync
uv run python --version
```

确认本地 `.env` 中有必要 API Key：

```text
ARK_API_KEY=...
DEEPSEEK_API_KEY=...
```

注意：

- `.env` 不能提交到 GitHub。
- 不要把 API Key 写进任何 Markdown、CSV、日志截图或聊天记录。
- 如果 API Key 不可用，实验会在 embedding 或答案生成阶段失败。

## 3. 输入文件

批量实验依赖三个核心输入文件：

```text
data/processed/documents.csv
data/testset/questions.csv
data/testset/references.csv
```

### documents.csv

记录知识库中有哪些文档。关键字段：

| 字段 | 含义 |
| --- | --- |
| `doc_id` | 文档编号，例如 `doc_001` |
| `title` | 文档标题 |
| `file_path` | 文档相对路径 |
| `doc_type` | 文档类型 |
| `source` | 来源说明 |
| `note` | 备注 |

当前脚本会读取这些文档，并统一切分为 chunk。

### questions.csv

记录测试题。关键字段：

| 字段 | 含义 |
| --- | --- |
| `question_id` | 问题编号，例如 `Q001` |
| `question` | 用户问题 |
| `task_type` | 任务类型 |
| `difficulty` | 难度 |
| `required_tool` | 预期是否需要工具 |
| `expected_path` | 预期主要由哪个配置解决 |
| `note` | 备注 |

当前批量脚本默认读取前 20 条问题。

### references.csv

记录参考答案和参考证据。关键字段：

| 字段 | 含义 |
| --- | --- |
| `question_id` | 对应问题编号 |
| `reference_answer` | 参考答案 |
| `evidence_doc_id` | 参考文档编号 |
| `evidence_chunk_id` | 参考 chunk 编号 |
| `citation_required` | 是否要求引用 |
| `judge_rule` | 人工评分规则 |

当前 `evidence_chunk_id` 还有较多 `pending`，所以现在只能先做文档级粗评估。正式评测前必须补齐 gold chunk。

## 4. 运行命令

建议每次正式运行前先做基础检查：

```powershell
uv run ruff check .
uv run pytest
```

再运行批量实验：

```powershell
uv run python run_batch_experiments.py
```

脚本会依次完成：

1. 读取 `documents.csv`。
2. 解析知识库文档。
3. 切分 chunk，写入 `data/processed/chunks.jsonl`。
4. 调用 embedding，构建统一内存向量索引。
5. 用同一索引跑 C0 的 20 条题。
6. 用同一索引跑 C1 的 20 条题。
7. 写入日志和结果表。

如果旧日志已经存在，脚本会先备份旧日志，再写入本次新日志。

## 5. 输出文件

运行成功后，应出现这些文件：

```text
runs/logs/c0_naive/run_logs.jsonl
runs/results/c0_results.csv
runs/logs/c1_rewrite/run_logs.jsonl
runs/results/c1_results.csv
data/processed/chunks.jsonl
```

### JSONL 日志

`run_logs.jsonl` 是程序级实验日志，一行对应一次问题运行。它用于追溯模型输入输出、检索证据、token、延迟和错误信息。

重点字段：

| 字段 | 含义 |
| --- | --- |
| `run_id` | 单次运行编号 |
| `config` | 配置名 |
| `question_id` | 问题编号 |
| `original_query` | 原始问题 |
| `retrieval_queries` | 实际检索 query |
| `retrieved_chunks` | Top-K 检索证据 |
| `answer` | 生成答案 |
| `citations` | 引用信息 |
| `latency_ms` | 延迟 |
| `token_usage` | token 统计 |
| `error` | 错误信息 |

C1 还会额外包含：

```text
need_rewrite
rewrite_confidence
rewrite_reason
rewrite_type
rewritten_query
rewritten_queries
```

当前 C1 会让 `retrieval_queries` 保留原始问题，并追加 `rewritten_queries` 中的多个候选检索 query。

### CSV 结果表

`c0_results.csv` 和 `c1_results.csv` 是方便人工查看和统计的表格。

重点字段：

| 字段 | 含义 |
| --- | --- |
| `top_contains_expected_doc` | Top-K 是否命中参考文档 |
| `top_rank_expected_doc` | 参考文档首次出现的排名 |
| `top_chunk_ids` | Top-K chunk 编号 |
| `top_doc_ids` | Top-K 文档编号 |
| `answer` | 答案 |
| `latency_ms` | 延迟 |
| `total_tokens` | 总 token |

注意：`top_contains_expected_doc=True` 只能说明检索到了参考文档，不等于答案一定正确。

## 6. 如何快速检查实验是否成功

运行完成后，可以用下面的检查逻辑：

```text
c0_naive/run_logs.jsonl 应有 20 行
c1_rewrite/run_logs.jsonl 应有 20 行
c0_results.csv 应有 20 行
c1_results.csv 应有 20 行
error 字段应为空
```

也可以人工打开 CSV，先看这些问题：

```text
Q005
Q007
Q013
```

当前初版实验中：

- Q007 是 C1 相比 C0 改善的例子。
- Q005 和 Q013 是 C0/C1 都没有命中预期文档的失败例子。

这些题很适合写进后续失败案例分析。

## 7. 结果怎么解释

当前 C0/C1 初版批量结果：

| 配置 | 错误数 | 预期文档命中 | 平均延迟 | 平均 token |
| --- | ---: | ---: | ---: | ---: |
| C0 | 0 | 17/20 | 7441 ms | 915 |
| C1 | 0 | 18/20 | 11073 ms | 1328 |

可以初步说明：

- C1 query rewrite 有一定帮助，但收益还不大。
- C1 会增加延迟和 token 成本。
- 目前还不能说明 C1 的答案质量一定优于 C0。

不能直接下的结论：

- 不能说 C1 已经显著优于 C0。
- 不能说 C1 在所有问题上都有效。
- 不能用文档级命中代替正式 Recall@K。
- 不能用工具型题目的 C0/C1 表现评价 C4 工具调用能力。

## 8. 下一步怎么做

短期下一步：

1. 补齐 `references.csv` 里的 `evidence_chunk_id`。
2. 人工检查 `c0_results.csv` 和 `c1_results.csv` 的答案正确性。
3. 标注 Answer Correctness 和 Citation Accuracy。
4. 整理成功案例和失败案例。
5. 建立 `docs/evaluation_plan.md`，固定评分规则。

然后再进入 C2：

1. 在同一知识库、同一测试集上开启 BM25/hybrid retrieval。
2. 增加 rerank。
3. 对比 C0、C1、C2。
4. 观察检索质量、答案质量、引用可信度、延迟和 token 成本变化。

## 9. 常见问题

### 报错：请配置环境变量 ARK_API_KEY

说明 `.env` 里没有 `ARK_API_KEY`，或者 `.env` 不在项目根目录。

处理：

```powershell
Copy-Item .env.example .env
```

然后在 `.env` 中填入真实 Key。

### 跑得很慢

正常。批量实验会调用 embedding、query rewrite 和答案生成 API。C1 比 C0 更慢，因为它多了一次 query rewrite。

### 日志里有旧结果

当前脚本会在写新日志前备份旧日志，并重新写入固定路径：

```text
run_logs.before_batch_*.jsonl
run_logs.jsonl
```

正式统计时只看本次的 `run_logs.jsonl`。

### 结果 CSV 已生成，能不能直接写报告？

不能。CSV 是程序输出，还需要人工检查和评分。结题报告中真正有说服力的是：

- 指标表；
- 成功案例；
- 失败案例；
- 模块消融；
- 成本分析。

### 跑完后要不要立刻 push？

不要自动 push。先让组长检查：

- 输出是否完整；
- 是否泄露 Key；
- 是否有不该提交的大文件；
- 是否需要提交代码、文档或只保留本地结果。
