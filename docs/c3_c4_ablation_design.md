# C3/C4 当前结论与消融实验设计

更新日期：2026-06-03

本文用于固定 C3/C4 当前阶段结论，并给出后续可直接执行的模块消融实验方案。AI Judge 结果只作为辅助，关键题仍需人工复核。

## 1. 当前结论

### 1.1 C3 当前结论

当前最强候选版本为 `C3-final`，对应命令口径为：

```powershell
uv run python run_c34_batch_eval.py `
  --tier c3 `
  --split ids `
  --question-ids Q001,Q002,Q003,Q004,Q005,Q006,Q007,Q008,Q009,Q010,Q011,Q012,Q013,Q014,Q015,Q016,Q017,Q018,Q019,Q020,Q021,Q022,Q023,Q024,Q025,Q026,Q027,Q028,Q029,Q030 `
  --planning-rewrite `
  --no-adaptive-route `
  --c3-final-opt
```

30 题 AI Judge 汇总如下：

| 配置 | 题数 | 平均延迟 ms | 平均 RAG 次数 | Answer | Citation | Faithfulness | 综合分 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C2 Stage2 old | 30 | 21195 | 1.00 | 0.683 | 0.667 | 0.950 | 0.738 |
| C2 Stage3 old | 30 | 20811 | 1.00 | 0.633 | 0.650 | 0.983 | 0.725 |
| C3 formal old | 30 | 156693 | 10.87 | 0.767 | 0.750 | 0.950 | 0.808 |
| C3-lite-next | 30 | 41613 | 1.60 | 0.750 | 0.717 | 0.967 | 0.796 |
| C3-final | 30 | 54930 | 2.27 | 0.833 | 0.900 | 0.900 | 0.867 |

阶段判断：

- `C3-final` 相比 `C3-lite-next` 提升答案质量和引用准确率，但平均延迟和 RAG 次数上升。
- `C3-final` 相比旧版 `C3 formal old` 大幅降低调用次数和延迟，同时综合分更高。
- `Q012/Q013/Q014` 仍是 C3 薄弱题，主要问题是复杂分类、表格归类和证据解释。
- `Q023` 答案可用，但引用支撑仍偏弱。
- 因此 `C3-final` 可以作为当前主候选，但冻结前必须人工复核重点题。

### 1.2 C4 当前结论

当前采用版结果文件为：

```text
runs/results/c4_candidates_optimized_results.csv
runs/results/c4_candidates_optimized_llm_judged.csv
runs/results/c4_candidates_optimized_summary.md
runs/results/c4_candidates_baseline_vs_optimized.csv
```

在 `Q031-Q048` 18 道 C4 候选题上，当前版本结果为：

| 指标 | 数值 |
| --- | ---: |
| 成功题数 | 18/18 |
| 平均延迟 | 约 18.30s |
| Answer Correctness | 0.833 |
| Citation Accuracy | 0.917 |
| Faithfulness | 0.972 |
| 综合分 | 0.903 |
| 工具选择匹配 | 16/18 |
| 工具输出被使用 | 17/18 |

阶段判断：

- C4 当前主要提升来自结构化工具调用日志、工具输出 ID 和 `[tool:...]` 引用绑定。
- C4 对文件读取、表格分析、计算器、代码执行、缺文件保守回答已经具备初步正式测试能力。
- `Q039/Q048` 是主要失败题，说明代码文件分析和 CSV 脚本执行仍不稳定。
- `Q044` 应单独按“缺文件保守回答成功”统计，不应按普通工具成功率简单判负。
- C4 当前结论是“初步正式结果”，尚未最终冻结。

## 2. C3 消融实验设计

### 2.1 消融组

| 组别 | 目的 | 命令差异 |
| --- | --- | --- |
| `C3-final-full` | 完整 C3-final 主候选 | `--c3-final-opt` |
| `C3-no-required-items` | 验证 required-items 覆盖与定向补检索贡献 | `--c3-final-opt --c3-ablate-required-items` |
| `C3-no-evidence-grader` | 验证 Evidence Grader 贡献 | `--c3-final-opt --c3-ablate-evidence-grader` |
| `C3-no-rrf` | 验证 multi-query RRF 贡献 | `--c3-final-opt --c3-ablate-rrf` |
| `C3-no-claim-check` | 验证 claim-level self-check 贡献 | `--c3-final-opt --c3-ablate-claim-check` |
| `C3-lite-next` | 历史轻量基线 | 使用既有结果 |
| `C3-formal-old` | 历史高成本基线 | 使用既有结果 |

### 2.2 C3 运行命令模板

```powershell
$ids = "Q001,Q002,Q003,Q004,Q005,Q006,Q007,Q008,Q009,Q010,Q011,Q012,Q013,Q014,Q015,Q016,Q017,Q018,Q019,Q020,Q021,Q022,Q023,Q024,Q025,Q026,Q027,Q028,Q029,Q030"

uv run python run_c34_batch_eval.py `
  --tier c3 `
  --split ids `
  --question-ids $ids `
  --planning-rewrite `
  --no-adaptive-route `
  --c3-final-opt `
  <ablation-flag> `
  --result-csv runs/results/c3_ablation_<name>_results.csv `
  --log-dir runs/logs/c3_ablation_<name>
```

评分命令：

```powershell
uv run python run_score_rag_multidim.py `
  --results runs/results/c3_ablation_<name>_results.csv `
  --questions runs/results/c3_final_30_questions_merged.csv `
  --references runs/results/c3_final_30_references_merged.csv `
  --out runs/results/c3_ablation_<name>_llm_judged.csv
```

### 2.3 C3 判定标准

- 关闭 required-items 后，如果 `Q012/Q013/Q025` 明显下降，说明 required-items 覆盖机制有效。
- 关闭 Evidence Grader 后，如果 Citation Accuracy 或 Faithfulness 下降，说明证据筛选有效。
- 关闭 RRF 后，如果 multi_doc 题覆盖下降，说明多查询融合有效。
- 关闭 claim-level self-check 后，如果 unsupported claim 或 citation mismatch 增多，说明自检有效。
- 若某模块只增加延迟但不提升质量，应记录为边界模块，不作为主结论强推。

重点人工复核题：

```text
Q012, Q013, Q014, Q023, Q025, Q027
```

## 3. C4 消融实验设计

### 3.1 消融组

| 组别 | 目的 | 命令差异 |
| --- | --- | --- |
| `C4-full-optimized` | 当前采用版 | 使用既有结果 |
| `C4-no-tools` | 验证外部工具整体必要性 | 同题用 `--tier c3 --c3-final-opt` 跑 |
| `C4-no-tool-citation` | 验证工具 citation 绑定贡献 | `--c4-ablate-tool-citation` |
| `C4-no-tool-priority-prompt` | 验证工具选择提示贡献 | `--c4-ablate-tool-priority-prompt` |
| `C4-no-file-reader` | 验证文件读取工具贡献 | `--disable-tools file_reader` |
| `C4-no-table-analyzer` | 验证表格分析工具贡献 | `--disable-tools table_analyzer` |
| `C4-no-calculator` | 验证计算器贡献 | `--disable-tools calculator` |
| `C4-no-code-runner` | 验证代码执行工具贡献 | `--disable-tools code_runner` |

### 3.2 C4 运行命令模板

```powershell
uv run python run_c34_batch_eval.py `
  --tier c4 `
  --split bank `
  --questions-csv data/testset/questions_c4_candidates.csv `
  --sandbox `
  --planning-rewrite `
  --max-rag-calls 3 `
  <ablation-flag> `
  --result-csv runs/results/c4_ablation_<name>_results.csv `
  --log-dir runs/logs/c4_ablation_<name>
```

`C4-no-tools` 对照命令：

```powershell
uv run python run_c34_batch_eval.py `
  --tier c3 `
  --split bank `
  --questions-csv data/testset/questions_c4_candidates.csv `
  --planning-rewrite `
  --no-adaptive-route `
  --c3-final-opt `
  --result-csv runs/results/c4_ablation_no_tools_results.csv `
  --log-dir runs/logs/c4_ablation_no_tools
```

评分命令：

```powershell
uv run python run_score_rag_multidim.py `
  --results runs/results/c4_ablation_<name>_results.csv `
  --questions data/testset/questions_c4_candidates.csv `
  --references data/testset/references_c4_candidates.csv `
  --out runs/results/c4_ablation_<name>_llm_judged.csv
```

### 3.3 C4 判定标准

- `C4-full` 必须显著优于 `C4-no-tools`，否则不能说明工具调用必要性。
- 禁用某类工具后，对应题型应明显下降；否则说明题目不能有效检验该工具。
- `C4-no-tool-citation` 若 Citation/Faithfulness 明显下降，说明工具引用绑定是 C4 可信度提升核心。
- `Q044` 单独按“缺文件保守回答成功”统计。
- `Q039/Q048` 保留为失败案例，用于说明代码分析工具仍需 AST/静态分析增强。

重点人工复核题：

```text
Q034, Q039, Q043, Q044, Q047, Q048
```

## 4. 输出文件建议

正式跑完消融后生成：

```text
runs/results/c3_ablation_summary.csv
runs/results/c4_ablation_summary.csv
runs/results/c3_c4_ablation_conclusion.md
```

汇总字段至少包括：

```text
config, question_count, avg_latency_ms, avg_rag_query_count,
avg_answer_correctness, avg_citation_accuracy, avg_faithfulness,
avg_weighted, avg_tool_selection_match, avg_tool_output_used,
key_failures, conclusion
```

## 5. 注意事项

- 不把 C3 简单题路由到 C2 的收益写成 C3 自身收益；C3 消融默认使用 `--no-adaptive-route`。
- 不把 C4 工具 citation 的评分提升写成“检索能力提升”；它属于工具证据可信度提升。
- `runs/` 默认不提交仓库，如需给组员或老师查看，应单独打包或明确提交。
- AI Judge 只作辅助，最终结论必须结合人工复核。
