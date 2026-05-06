# C0-C1 工程接口与日志规范

本文档用于固定 C0 与 C1 的输入、输出和日志结构。即使 C0 代码后续还要整理，C1、C2、评测脚本和组员协作也必须优先对齐这些数据结构。

## 1. 总原则

- C1 只在 C0 基础上增加 query rewrite，不加入 BM25、rerank、多轮检索、任务规划、工具调用或 self-check。
- 所有实验配置都必须输出同一类 `RunResult` 字典，便于后续统一写入 `runs/logs/*.jsonl` 和 `runs/results/*.csv`。
- 每次运行都要保留原始问题、实际用于检索的查询、Top-K 证据、答案、引用、耗时和错误信息。
- 如果某一步失败，不要让程序静默跳过；日志中的 `error` 字段必须记录失败原因。

## 2. 输入结构 QueryTask

最小输入字段如下：

```json
{
  "question_id": "Q001",
  "question": "用户原始问题",
  "task_type": "fuzzy_qa",
  "doc_scope": ""
}
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `question_id` | 建议必填 | 测试题编号，用于和参考答案、日志、结果表对齐。 |
| `question` | 必填 | 用户原始问题，不允许在进入 C1 前手工改写。 |
| `task_type` | 可选 | 任务类型，如 `simple_qa`、`fuzzy_qa`、`evidence_location`、`tool_task`。 |
| `doc_scope` | 可选 | 限定检索范围；为空表示检索当前知识库。 |

## 3. C1 Query Rewrite 输出结构

C1 的 query rewrite 模块输出 `RewriteResult`：

```json
{
  "need_rewrite": true,
  "rewrite_confidence": 0.85,
  "rewrite_reason": "原问题存在口语化表达，检索关键词不足",
  "rewrite_type": "colloquial",
  "rewritten_query": "最重要的单个检索 query",
  "rewritten_queries": [
    "语义检索 query",
    "关键词检索 query",
    "实体、文件名、代码名相关 query"
  ],
  "raw_output": "LLM 原始输出",
  "token_usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0
  }
}
```

约束：

- `rewritten_query` 必须保留原问题意图。
- `rewritten_queries` 用于保存多个候选检索 query，最多 3-4 个，不能引入用户没有提到的新目标。
- `rewrite_confidence` 低于阈值时视为不改写，避免清晰问题被乱改。
- 代码标识符、数字、公式、文件名、专有名词不能随意改动。
- 如果原问题已经清楚，`need_rewrite=false`，`rewritten_query` 保持原问题。
- C1 检索默认使用 `original_plus_multi_candidate_rewritten` 策略，即保留原始问题，并追加多个改写后的检索 query。

## 4. 证据结构 EvidenceChunk

检索输出的每条证据统一为：

```json
{
  "chunk_id": "doc_001::chunk_0001",
  "doc_id": "doc_001",
  "text": "证据片段文本",
  "score": 0.83,
  "source": "原始文件路径或文档来源",
  "page": null,
  "rank": 1,
  "query": "触发该证据的检索查询"
}
```

说明：

- `chunk_id` 是评测引用的最小单位，后续计算 Citation Accuracy 时优先用它对齐。
- `score` 是当前检索器的分数，C0/C1 为向量余弦相似度。
- `query` 用于分析 C1 是否因为改写查询找到了更好的证据。

## 5. 运行输出 RunResult

C0 输出：

```json
{
  "run_id": "c0-...",
  "config": "c0_naive",
  "question_id": "Q001",
  "original_query": "用户原始问题",
  "retrieval_queries": ["用户原始问题"],
  "retrieved_chunks": [],
  "answer": "最终答案",
  "citations": [],
  "latency_ms": 1200,
  "token_usage": {
    "answer_generation": {}
  },
  "token_cost": null,
  "error": ""
}
```

C1 在 C0 基础上额外增加：

```json
{
  "need_rewrite": true,
  "rewrite_confidence": 0.85,
  "rewrite_reason": "改写原因",
  "rewrite_type": "colloquial",
  "rewritten_query": "最重要的单个检索 query",
  "rewritten_queries": ["候选 query 1", "候选 query 2"]
}
```

## 6. C1 验收标准

C1 完成后至少要通过以下检查：

| 类别 | 验收标准 |
| --- | --- |
| 模块边界 | C1 只新增 query rewrite，不出现 BM25、rerank、多轮检索、工具调用或 self-check。 |
| JSON 稳定性 | 10 条样例中 query rewrite 输出能被解析为 JSON 的比例为 100%。 |
| 改写有效性 | 人工抽查的 Rewrite Validity 平均分不低于 0.8。 |
| 保真性 | 改写不改变原问题目标，不丢失代码名、公式、数字和关键术语。 |
| 日志完整性 | 每条运行日志包含 `original_query`、`need_rewrite`、`rewrite_confidence`、`rewritten_query`、`rewritten_queries`、`retrieval_queries`、`retrieved_chunks`、`answer`、`citations`、`latency_ms`、`error`。 |
| 对比可运行 | 同一批测试题可以分别跑 C0 和 C1，并输出同结构结果。 |

Rewrite Validity 人工评分建议：

- `1`：改写保留原意，并明显更适合检索；
- `0.5`：改写基本保留原意，但补充关键词有限；
- `0`：改写改变问题、引入无关内容或丢失关键信息。

## 7. C1 测试办法

优先完成三类测试：

1. 单元测试：测试 JSON 提取、改写结果规范化、检索查询构造。
2. 接口测试：测试 C0/C1 输出字段是否满足本文件定义。
3. 小样例对比：选 5-10 条模糊问题，人工比较 C0 与 C1 的 Top-K 证据是否更贴近参考答案。

正式实验前，测试集、Prompt、配置文件和模型名称都要冻结，并在 `docs/experiment_notes.md` 中记录版本。
