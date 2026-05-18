# C3 小批量验证实验说明

本文档说明如何复现当前 C3 小批量验证实验。C3 当前不是 C0/C1/C2 那种独立批量脚本线，而是通过 `main.py agent --c3` 走 Agent 编排线，因此本阶段定位为 smoke test：先验证 C3 是否能稳定完成规划、检索工具调用、多查询执行和证据覆盖，再决定是否开发正式 C3 批量实验脚本。

## 1. 实验目标

本轮 C3 验证关注以下问题：

- C3 入口是否能稳定运行，不出现程序级错误。
- 是否能生成任务规划，并调用 `topic4_rag_query` 检索工具。
- 是否出现多查询、多 pipeline 或多次 RAG 调用行为。
- gold doc / gold chunk 是否比单次检索更容易覆盖。
- 是否存在明显缺陷，例如延迟过高、证据覆盖不足、过度拒答、引用不准或网络中断。

本轮结果不能直接作为 C3 正式结论，只能作为 C3 进入正式实验前的可运行性和缺陷定位依据。

## 2. 测试题范围

测试题来自：

```text
data/testset/questions_c3_candidates.csv
data/testset/references_c3_candidates.csv
```

题号范围：

```text
Q021-Q030
```

题目分层：

| 类别 | 题号 | 作用 |
| --- | --- | --- |
| 基础验收题 | Q022, Q024, Q026, Q028, Q030 | 验证 C3 主流程是否稳定 |
| 多轮检索题 | Q021, Q023, Q025 | 验证任务规划、子查询拆解、多次检索 |
| 压力测试题 | Q027, Q029 | 暴露模糊查询、证据不足和高延迟问题 |

## 3. 前置检查

在项目根目录执行：

```powershell
git status --short --branch
git log -1 --oneline
uv run python --version
uv run pytest tests/test_deep_planning_presets.py tests/test_session_planner_json.py tests/test_runtime_tools.py tests/test_runtime_state.py
```

当前已验证：

```text
Python 3.12.10
13 passed
```

注意：Windows PowerShell 默认编码可能导致 C3 控制台输出出现 `UnicodeEncodeError`。批量运行时建议设置：

```powershell
$env:PYTHONIOENCODING="utf-8"
$env:PYTHONUTF8="1"
```

## 4. 单题运行命令

单题调试命令：

```powershell
uv run python main.py agent --c3 --planning-rewrite --json --once "<题目文本>"
```

参数说明：

- `--c3`：启用 C3 Agentic Retrieval 模式，只允许检索工具，不启用 C4 外部工具。
- `--planning-rewrite`：在第一层规划前加入 C1 同源 query rewrite，帮助处理模糊和多文档问题。
- `--json`：输出 messages debug，便于后续解析工具调用、检索证据和模型回答。
- `--once`：单题非交互运行。

## 5. 输出文件

本轮运行输出到：

```text
runs/results/c3_smoke_results.csv
runs/logs/c3_agentic_retrieval/run_logs.jsonl
runs/logs/c3_agentic_retrieval/summary.json
runs/logs/c3_agentic_retrieval/Q021_console.txt
...
runs/logs/c3_agentic_retrieval/Q030_console.txt
```

说明：

- `runs/` 默认不提交仓库。
- `Qxxx_console.txt` 是逐题完整控制台日志，供人工复查。
- `c3_smoke_results.csv` 是半自动整理结果，不等于最终人工评分。
- `summary.json` 是本轮 smoke test 摘要。

## 6. 当前结果摘要

本轮有效结果：

| 指标 | 结果 |
| --- | ---: |
| 总题数 | 10 |
| 程序级错误 | 0 |
| RAG 调用 | 10/10 |
| 多查询 / 多 pipeline 行为 | 10/10 |
| 平均延迟 | 152038 ms |
| 平均 gold doc 覆盖率 | 0.9000 |
| 平均 gold chunk 覆盖率 | 0.6067 |

逐题覆盖情况：

| 题号 | 类别 | gold doc 覆盖 | gold chunk 覆盖 | 延迟(ms) |
| --- | --- | ---: | ---: | ---: |
| Q021 | 多轮检索 | 2/3 | 1/3 | 138887 |
| Q022 | 基础验收 | 4/4 | 3/4 | 136057 |
| Q023 | 多轮检索 | 5/5 | 3/5 | 133619 |
| Q024 | 基础验收 | 3/3 | 5/6 | 126346 |
| Q025 | 多轮检索 | 2/3 | 3/6 | 196684 |
| Q026 | 基础验收 | 3/3 | 4/5 | 114438 |
| Q027 | 压力测试 | 2/3 | 1/3 | 178996 |
| Q028 | 基础验收 | 3/3 | 2/4 | 139056 |
| Q029 | 压力测试 | 2/2 | 2/3 | 282236 |
| Q030 | 基础验收 | 1/1 | 3/4 | 74062 |

## 7. 初步结论

C3 目前已经可以跑通，且能体现 Agentic Retrieval 的关键行为：规划后调用 RAG 工具、多次检索、多 pipeline 选择和证据整合。

但 C3 还不能冻结，主要原因是：

- 延迟明显偏高，平均单题约 152 秒，Q029 超过 280 秒。
- gold doc 覆盖较好，但 gold chunk 覆盖只有约 60.67%。
- Q021、Q025、Q027 的证据覆盖偏弱，说明复杂拆解和模糊查询仍需优化。
- 当前 `c3_smoke_results.csv` 还没有人工 `Answer Correctness` 和 `Citation Accuracy`。

## 8. 下一步验收

唐宁需要基于以下文件进行人工检查：

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

人工评分重点：

- 答案是否正确、完整、没有无证据扩展。
- 引用是否真正支撑答案。
- 是否有清晰任务规划。
- 是否有必要的子查询拆解。
- 多次检索是否带来有效证据，而不是重复消耗 token。
- 压力题失败时，失败原因是 query planning、检索覆盖、证据不足、self-check 还是网络/API 问题。

## 9. 后续改进方向

当前不建议立刻冻结 C3。建议先完成人工评分，再决定是否优化：

1. 限制 C3 单题最大执行时间和最大 RAG 调用次数。
2. 让 planner 显式输出子查询列表，便于评测多轮检索是否合理。
3. 对 Q021、Q025、Q027 增强子查询拆解规则。
4. 将 C3 smoke test 固化为正式批量脚本，输出格式对齐 C0/C1/C2。
5. 再与 C2 Stage2 / Stage3 做同题对比，判断 C3 是否真正提升答案质量。
