# C3 30 题完整版实验报告

生成日期：2026-05-24  
实验阶段：C3 Agentic Retrieval RAG 正式批量验证  
实验性质：C3 完整版实验。本轮使用当前默认 C3 编排配置，并开启 planning-rewrite。

## 1. 实验目的

本次实验用于验证 C3 Agentic Retrieval RAG 在 30 道题上的完整运行效果，重点观察：

- 第一层任务规划 planning；
- 规划前 query rewrite；
- 查询拆解 / 多子查询；
- 多次 RAG 检索；
- 多 pipeline 选择；
- 第三层 judge / self-check 对答案完成度的影响；
- 完整 C3 在效果、延迟和调用成本上的收益边界。

本轮只跑 C3，不跑 C2 同题对照。因此本报告只能说明 C3 自身表现、优点、缺点和适用边界，不能直接证明 C3 相比 C2 有显著提升。

## 2. 实验配置

题目范围为 Q001-Q030 共 30 道题：

- Q001-Q020：主测试集，覆盖 simple_qa、fuzzy_query、multi_doc、table_analysis、calculation、code_execution、insufficient_evidence 等任务类型；
- Q021-Q030：C3 候选题，主要覆盖多文档整合、模糊需求和证据不足判断。

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

每题按默认 C3 完整编排执行。当前默认配置允许多轮规划、执行和研判，能够更充分体现 C3 Agentic Retrieval 的能力，但也会显著增加延迟、RAG 调用次数和 API 成本。

实验前执行 `uv run python main.py kb sync`，本轮知识库同步状态为：

```text
document_count = 25
chunk_count = 482
index = SimpleVectorIndex
embedding_cache = data/processed/kb_embedding_cache.pkl
```

说明：本轮 C3 使用的是自实现轻量内存向量索引，不是 Chroma 向量数据库。

## 3. 输出文件

本次实验生成的主要文件如下：

```text
runs/results/c3_ids_results.csv
runs/results/c3_formal_30_llm_judged.csv
runs/results/c3_formal_30_questions.csv
runs/results/c3_formal_30_references.csv
runs/logs/c3_agentic_retrieval_30_batch_full_20260524/run_logs.jsonl
runs/logs/c3_agentic_retrieval_30_batch_full_20260524/batch_report.json
```

说明：

- `c3_ids_results.csv` 是 C3 完整版正式批量运行结果表；
- `c3_formal_30_llm_judged.csv` 是 AI Judge 辅助评分结果；
- `run_logs.jsonl` 是逐题运行日志；
- `batch_report.json` 记录本次运行环境、参数、知识库 hash 和每题 session 信息；
- `runs/` 默认被 `.gitignore` 忽略，不自动提交仓库。

## 4. 总体结果

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
| AI Judge 跳过数 | 0 |
| AI Judge Answer Correctness | 0.7667 |
| AI Judge Answer Completeness | 0.7667 |
| AI Judge Citation Accuracy | 0.7500 |
| AI Judge Faithfulness | 0.9500 |
| AI Judge 加权综合分 | 0.8083 |

验收标准对照：

| 验收项 | 结果 | 判断 |
| --- | ---: | --- |
| 30 题全部生成记录 | 30/30 | 达到 |
| 程序级 error 为 0 | 0 | 达到 |
| `topic4_rag_query` 调用题数不少于 9/10 | 30/30 | 达到 |
| 至少 6/10 题出现多查询或多轮检索行为 | 22/30 | 达到 |
| 平均 gold doc coverage 不低于 0.85 | 0.9228 | 达到 |
| 平均 gold chunk coverage 不低于 0.60 | 0.6975 | 达到 |

总体看，C3 完整版能够稳定产生多轮检索行为，并在复杂多文档任务上取得较高证据覆盖；但延迟和检索调用次数明显升高，AI Judge 对答案正确性和完整性的评分没有达到同等幅度提升，说明“更多轮检索”不必然带来更高答案质量。

## 5. 分组结果

按题目来源分组：

| 分组 | 题数 | 平均延迟(ms) | 平均 RAG 调用 | gold doc coverage | gold chunk coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| Q001-Q020 主测试集 | 20 | 138348.75 | 8.95 | 0.9008 | 0.6246 |
| Q021-Q030 C3 候选题 | 10 | 193382.4 | 14.7 | 0.9667 | 0.8433 |

按任务类型分组：

| 任务类型 | 题数 | 平均延迟(ms) | 平均 RAG 调用 | gold doc coverage | gold chunk coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| simple_qa | 4 | 65450.5 | 3.75 | 1.0000 | 0.3458 |
| fuzzy_query | 5 | 127184.6 | 7.4 | 0.7033 | 0.6038 |
| multi_doc | 12 | 201151.0 | 15.5 | 1.0000 | 0.8478 |
| table_analysis | 3 | 326850.67 | 20.6667 | 0.9444 | 0.4500 |
| calculation | 2 | 24444.5 | 1.0 | 1.0000 | 1.0000 |
| code_execution | 2 | 36466.5 | 1.5 | 1.0000 | 0.8334 |
| insufficient_evidence | 2 | 143444.0 | 10.5 | 0.6666 | 0.6666 |

从分组结果看：

1. C3 完整版对多文档任务最有价值，`multi_doc` 的 gold chunk coverage 达到 0.8478，但代价是平均 15.5 次 RAG 调用和约 201 秒延迟。
2. 简单问答不适合走完整 C3。`simple_qa` 文档覆盖为 1.0，但 chunk coverage 只有 0.3458，同时平均耗时约 65 秒。
3. 工具型任务不适合 C3 硬答。`table_analysis` 平均延迟超过 326 秒，chunk coverage 只有 0.45，应交给 C4 工具调用。
4. 证据不足任务在本轮表现不稳定，doc coverage 只有 0.6666，说明完整 C3 仍需要更明确的“证据不足时保守回答”策略。

## 6. 重点问题

以下题目存在较明显覆盖不足：

| 题号 | 类型 | 主要问题 |
| --- | --- | --- |
| Q001 | simple_qa | gold doc 命中但 gold chunk coverage 为 0，引用定位不精确 |
| Q002 | simple_qa | gold chunk coverage 仅 0.3333，简单题仍有证据定位问题 |
| Q004 | simple_qa | gold chunk coverage 仅 0.25 |
| Q007 | fuzzy_query | gold doc coverage 仅 0.25，虽然检索 11 次但方向仍偏 |
| Q008 | fuzzy_query | gold doc coverage 0.6，模糊查询仍漏关键文档 |
| Q013 | table_analysis | 检索 13 次但 gold chunk coverage 为 0，C3 不适合表格分析 |
| Q014 | table_analysis | 延迟高，文档覆盖略低 |
| Q020 | insufficient_evidence | 文档与 chunk 覆盖均为 0.3333，证据不足判断不稳 |
| Q027 | fuzzy_query | 文档覆盖 0.6667，模糊需求定位仍需优化 |

AI Judge 低分题包括：

| 题号 | 主要评分问题 |
| --- | --- |
| Q007 | 答案不完整 |
| Q008 | 答案不完整或偏离 |
| Q009 | off_topic |
| Q012 | wrong_answer |
| Q013 | 表格题回答质量差 |
| Q014 | 答案不完整 |
| Q017 | 答案不完整 |
| Q023 | 答案不完整 |

这些题需要人工复核，因为 AI Judge 只能作为辅助参考。正式结论仍应以人工 Answer Correctness、Citation Accuracy、planning_quality 和 retrieval_sufficiency 为准。

## 7. 阶段性结论

1. C3 完整版已经具备稳定批量运行能力，30 题全部完成且无程序级错误。
2. C3 完整版确实能体现 Agentic Retrieval 行为：平均每题 10.8667 次 RAG 调用，多次检索题数为 22/30。
3. C3 完整版的 gold chunk coverage 达到 0.6975，说明多轮检索有助于覆盖更细粒度证据。
4. 但更多轮检索没有必然带来更高答案质量。AI Judge 综合分为 0.8083，说明 C3 容易出现“检索更多但答案更散”的问题。
5. C3 更适合多文档整合任务，不适合简单问答、表格分析、计算和代码执行等任务。
6. C3 完整版延迟不可忽视：平均约 157 秒，p95 约 480 秒；若作为 Demo 或正式系统，需要路径选择或调用次数控制。
7. 本轮启用了 planning-rewrite，因此报告中应写作“C3 完整版 + planning-rewrite”，不能把全部效果归因于 C3 planning。
8. 若要证明 C3 相比 C2 的增益，后续必须用同一批 Q001-Q030 或至少 Q021-Q030 跑 C2 Stage2 / Stage3 同题对照。

## 8. 改进方向

1. 增加路径选择：simple_qa、calculation、code_execution 直接走 C2 或 C4，不强制完整 C3。
2. 限制重复检索：对同一题中高度相似的子查询做去重，避免 Q009、Q013 这类多次检索但答案质量下降的情况。
3. 改进 planner prompt：要求第一层显式输出子问题列表、每个子问题的目的和停止条件。
4. 改进 citation 选择：最终答案不要把所有检索 chunk 都作为引用，应只保留真正支撑答案的 chunk。
5. 强化证据不足策略：对 insufficient_evidence 任务，应优先输出“现有资料不足以证明”，而不是继续扩大检索范围。
6. 工具型任务进入 C4：Q013、Q016-Q019 应用于验证表格分析、计算器和代码执行工具，而不是用 C3 检索硬答。

## 9. 后续工作

1. 唐宁建立人工评分文件：

```text
data/testset/manual_eval_c3_formal.csv
```

建议字段：

```csv
question_id,answer_correctness,citation_accuracy,planning_quality,multi_round_quality,retrieval_sufficiency,self_check_quality,main_problem,comment,reviewer,status
```

2. 人工优先复盘：

```text
Q007, Q008, Q009, Q012, Q013, Q020, Q023, Q027, Q029
```

3. 赵启行整理报告口径：

- C3 完整版能提升复杂多文档任务的证据覆盖；
- C3 完整版成本高，不适合所有任务；
- C3 当前不能直接写成“显著优于 C2”，需要同题 C2 对照；
- C3 与 C4 的边界要清楚：工具型任务应交给 C4。

4. 李金航后续若继续做 C4，应优先用 Q013、Q016-Q019 验证工具调用是否能解决 C3 在表格、计算和代码执行任务上的局限。
