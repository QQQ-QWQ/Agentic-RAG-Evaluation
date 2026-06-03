# Topic4 Agentic RAG Evaluation 当前进度

更新日期：2026-05-27

本文档用于同步仓库当前进度、阶段结论、运行入口、主要风险和下一步分工。  
根目录 `README.md` 主要保留课题定位、参考文献和项目总览；本文档负责记录动态进度。  
详细实验记录见 `docs/experiment_notes.md`，C3 优化技术说明见 `docs/c3_lite_optimization_technical_report.md`。

## 1. 当前阶段判断

当前项目处于：

```text
C3 低成本优化版阶段性完成 + C2 Stage3 回退收口 + C4 正式实验准备阶段
```

当前重点已经不是继续堆功能，而是：

- 固定 C2/C3 的正式结论口径；
- 补齐人工评分与失败案例；
- 开始 C4 工具调用任务的 smoke 与正式实验；
- 后续再做 Benchmark 子集和 Dify / RAGFlow 横向参考。

## 2. 模块状态总览

| 模块 | 当前状态 | 阶段判断 |
| --- | --- | --- |
| C0 Naive RAG | 已完成 20 题批量实验和人工评分 | 阶段性冻结 |
| C1 Query Rewrite | 已完成优化版 C1 和 20 题批量实验 | 阶段性冻结 |
| C2 Stage1 Hybrid | 已完成复现实验 | 作为 C2 消融对照 |
| C2 Stage2 Hybrid + Rerank | 已完成复现实验和人工评分 | 当前 C2 主基线 |
| C2 Stage3 Context Expansion | 当前代码已回退到旧版口径 | 仅作为上下文扩展边界对照 |
| C3 Agentic Retrieval | C3-lite-next 已完成 30 题实验 | 当前 C3 主方案，待人工复核重点题 |
| C4 Tool-Augmented Agentic RAG | 工具链路和 batch 入口已有基础 | 下一阶段重点 |
| AI Judge | 多维评分脚本已接入 | 只能辅助，不能替代人工评分 |
| Benchmark 子集 | 尚未正式开始 | C3/C4 稳定后再做 |
| Dify / RAGFlow 横向参考 | 尚未正式开始 | C5 横向参考，不参与 C0-C4 消融 |

## 3. C2 当前结论

### 3.1 C2 主基线

C2 当前主基线为：

```text
C2 Stage2 = C1 Query Rewrite + Hybrid Retrieval + Rerank
```

原因：

- 相比 C0/C1，C2 Stage2 的检索质量和答案质量更稳定；
- 相比 Stage3，Stage2 的成本更低、噪声更少；
- 当前结论更适合作为后续 C3/C4 的对照基线。

### 3.2 C2 Stage3 回退

此前尝试过 C2 Stage3 next：在上下文扩展后叠加 Evidence Grader 和更小上下文预算。  
30 题结果显示该版本退化：

| 配置 | 成功题数 | 平均延迟 | Answer Correctness | Citation Accuracy | Faithfulness | 综合分 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| C2 Stage2 old | 30/30 | 21.2s | 0.683 | 0.667 | 0.950 | 0.738 |
| C2 Stage3 old | 30/30 | 20.8s | 0.633 | 0.650 | 0.983 | 0.725 |
| C2 Stage3 next | 30/30 | 26.0s | 0.533 | 0.617 | 0.950 | 0.658 |

因此：

- C2 Stage3 next 已本地备份；
- `c2_stage3_context` 代码口径已回退；
- C2 Stage3 后续只作为“上下文扩展边界分析”，不作为主增强结论。

当前 C2 Stage3 代码口径：

```text
C2 Stage2 + context_neighbor_chunks=1
use_evidence_grader=False
context_max_expanded_hits=3
context_max_chars=6000
```

本地备份目录：

```text
archive/experiment_runs/c2_stage3_next_before_rollback_2026-05-27/
```

该目录不提交 Git。

## 4. C3 当前结论

### 4.1 当前 C3 主方案

当前 C3 主方案为：

```text
C3-lite-next
```

运行口径：

```text
--planning-rewrite
--no-adaptive-route
--c3-conservative-opt
```

说明：

- 开启 planning rewrite，用于改善模糊题和复杂题的规划前理解；
- 关闭 adaptive route，避免把“简单题走 C2”的收益误写成 C3 自身收益；
- 开启 conservative opt，包含 RAG 查询预算、重复查询抑制、Evidence Grader、claim-citation binding 和 claim-level self-check。

### 4.2 C3 优化内容

C3-lite-next 的核心优化包括：

- RAG 查询预算：避免旧版 C3 无限拆问题；
- multi-query RRF：多子查询结果先去重融合，再进入 rerank / answer generation；
- Evidence Grader：答案生成前过滤无关或背景证据；
- required-items 覆盖清单：减少多对象题漏项；
- claim-citation binding：要求核心 claim 绑定直接 citation；
- claim-level self-check：输出 unsupported claims、missing required items、citation mismatches 和 revision instruction。

完整技术说明：

```text
docs/c3_lite_optimization_technical_report.md
```

30 题实验结果记录：

```text
docs/c3_lite_next_30_experiment_report.md
```

### 4.3 C3 30 题结果

| 配置 | 成功题数 | 平均延迟 | 平均 RAG 次数 | Answer Correctness | Citation Accuracy | Faithfulness | 综合分 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C3 formal old | 30/30 | 156.7s | 10.87 | 0.767 | 0.750 | 0.950 | 0.808 |
| C3 conservative old | 30/30 | 98.3s | 5.37 | 0.733 | 0.767 | 0.917 | 0.792 |
| C3-lite-next | 30/30 | 41.6s | 1.60 | 0.750 | 0.717 | 0.967 | 0.796 |

阶段性判断：

- C3-lite-next 显著降低延迟和 RAG 调用次数；
- 综合分基本保持旧版 C3 水平；
- Answer Correctness 和 Faithfulness 提升；
- Citation Accuracy 略降，主要原因是引用数量收缩，平均 citation 从旧版约 7.4 降到 3.67，更容易漏掉 gold chunk；
- 这不是完全失败，而是从“重型宽引用 C3”转向“轻量聚焦 C3”的代价。

后续不能只追求 Citation Accuracy 最高。应同时看：

```text
Answer Correctness
Faithfulness
Citation Accuracy
Final Citation Count
Latency
RAG Query Count
```

理想目标是：答案正确、证据忠实、引用准确、引用数量适中、成本可接受。

## 5. 参考项目与外部对照

### 5.1 C3 技术机制参考

| 来源 | 借鉴内容 | 本项目对应实现 |
| --- | --- | --- |
| Self-RAG | 按需检索、自我批判、证据支撑判断 | claim-level self-check |
| CRAG | 文档相关性评估、检索纠错 | Evidence Grader |
| LangGraph Self-RAG / CRAG | retrieve -> grade -> generate -> check 流程 | C3 分层编排 |
| agentic-rag-for-dummies | 多查询、上下文压缩、自纠错、模块化 ARAG | 查询预算、RRF、证据压缩 |
| RRF 检索融合思想 | 多查询结果去重融合 | multi-query RRF |

### 5.2 评测思想参考

| 来源 | 借鉴内容 | 本项目对应指标 |
| --- | --- | --- |
| RAGAS | faithfulness、answer correctness、context 指标 | Answer Correctness、Faithfulness、Citation Accuracy |
| ARES | LLM 辅助评测 RAG 答案 | AI Judge |
| RAGChecker | 检索错误、生成错误、证据错误拆分 | main problem / failure type |
| RAGTruth | unsupported claim、错误拒答等问题分类 | unsupported_claims、over-refusal |

### 5.3 Dify / RAGFlow

Dify / RAGFlow 目前尚未完成正式横向实验，不能写成已完成对比。

后续建议放在 C5：

- 使用同一知识库；
- 使用同一测试题；
- 尽量使用同一模型；
- 记录答案质量、引用可信度、响应延迟；
- 不参与 C0-C4 模块消融，只作为市面/开源系统横向参考。

## 6. 当前仓库运行入口

### 6.1 环境准备

```powershell
uv sync
uv sync --group agent
uv run python main.py kb sync
```

`.env` 中至少需要：

```text
ARK_API_KEY=your_key_here
DEEPSEEK_API_KEY=your_key_here
```

C4 工具链可选：

```text
FIRECRAWL_API_KEY=...
SANDBOX_ENABLED=true
SANDBOX_TIMEOUT_SEC=60
FILE_WRITE_ENABLED=true
SHELL_COMMAND_ENABLED=true
SHELL_TIMEOUT_SEC=60
```

### 6.2 常用命令

| 任务 | 命令 |
| --- | --- |
| 知识库同步 | `uv run python main.py kb sync` |
| C0/C1 批量实验 | `uv run python main.py experiment batch` |
| C2 三阶段消融 | `uv run python main.py experiment c2 --phase all --limit 20` |
| C3 批量实验 | `uv run python run_c34_batch_eval.py --tier c3 --split ids --question-ids <ids>` |
| C4 工具题实验 | `uv run python run_c34_batch_eval.py --tier c4 --split c4_tools --sandbox --verbose-events` |
| AI Judge 评分 | `uv run python run_score_rag_multidim.py --results <csv> --questions <csv> --references <csv> --out <csv>` |
| Gradio 客户端 | `uv run python main.py client` |
| 日志查看页 | `uv run python main.py logs` |
| 单元测试 | `uv run pytest -q` |
| 静态检查 | `uv run ruff check .` |

## 7. 当前主要风险

### 7.1 人工评分仍需补齐

AI Judge 只能辅助判断，不能替代人工评分。  
尤其是 C3-lite-next 的以下题需要人工复核：

```text
Q005, Q006, Q012, Q015, Q023, Q027
```

复核重点：

- 是否漏 required items；
- claim 是否有直接 citation；
- citation 是否只是相关但不支撑结论；
- 是否把分类体系混淆；
- 是否过度拒答或证据不足仍下结论。

### 7.2 C4 尚未正式完成

C4 工具链已有基础，但还没有形成完整正式实验结论。  
后续必须明确：

- 哪些题是真正工具型题；
- 是否成功选择工具；
- 工具调用是否成功；
- 工具输出是否被答案正确使用；
- C4 相比 C3 的收益是否来自工具，而不是普通检索。

### 7.3 Benchmark 与开源系统横向参考尚未开始

公共 Benchmark 子集和 Dify / RAGFlow 横向参考还没做。  
这不是当前阻塞项，但最终报告中要明确：

- 自建测试集是主实验；
- Benchmark 子集是权威样例参考；
- Dify / RAGFlow 是横向系统参考；
- 不能把尚未完成的横向对比写成已有结果。

## 8. 下一步分工

### 赵启行

- 统筹 C3-lite-next 结论口径；
- 检查报告中 C2 Stage3、C3、Citation Accuracy 的表述是否严谨；
- 组织 C4 工具型题 smoke 与正式实验；
- 准备最终汇报中的技术路线图和模块消融表。

### 唐宁

- 人工复核 C3-lite-next 重点题：
  `Q005, Q006, Q012, Q015, Q023, Q027`；
- 标注 Answer Correctness、Citation Accuracy、Faithfulness、main problem；
- 对 AI Judge 与人工判断冲突的题写说明；
- 补齐 C4 工具题的 gold answer / expected tool。

### 李金航

- 解释 C3-lite 技术模块：
  查询预算、RRF、Evidence Grader、claim-level self-check；
- 协助定位 C3 失败题是检索问题、证据筛选问题还是答案生成问题；
- 推进 C4 工具调用链路稳定性；
- 准备 C4 工具调用日志字段和验收标准。

## 9. 当前可写入汇报的阶段性结论

可以写：

```text
本课题已完成 C0/C1/C2 基线与 C3-lite 低成本优化版的阶段性实验。
C2 Stage2 是当前最稳定的检索增强主基线；C2 Stage3 上下文扩展收益不稳定，
因此仅作为边界对照。C3-lite-next 在 30 题上以显著低于旧版 C3 的延迟和
RAG 调用次数，保持接近旧版 C3 的综合质量，并在复杂多文档、模糊查询和
证据不足任务上表现出更高价值。但当前 Citation Accuracy 因引用收缩略有下降，
后续需要在不回到宽引用的前提下继续优化 citation selection。
```

不能写：

```text
C3 全面优于 C2。
C2 Stage3 是稳定提升方案。
Dify / RAGFlow 已经完成横向对比。
AI Judge 可以替代人工评分。
Citation Accuracy 下降说明 C3 优化失败。
```

## 10. 提交规范提醒

不要提交：

```text
.env
.venv/
runs/
archive/
debug-*.log
__pycache__/
```

实验结果如需共享，应单独打包或在文档中摘要说明，不直接把 `runs/` 全量提交到 Git。


## 11. 2026-06-02 C4 当前正式口径更新

当前 C4 已从“准备阶段”推进到“初步正式实验完成 + 回退收口阶段”。本轮结论采用“上次优化版”作为当前正式口径，最新一次针对 Q039/Q048 的更激进 prompt 尝试已经回退，仅作为失败尝试和边界分析材料保留。

### 11.1 当前采用版本

当前采用版本由以下日志和结果重建：

- 日志目录：`runs/logs/c4_candidates_optimized_v4/`
- 结果表：`runs/results/c4_candidates_optimized_results.csv`
- AI Judge 评分：`runs/results/c4_candidates_optimized_llm_judged.csv`
- 汇总报告：`runs/results/c4_candidates_optimized_summary.md`
- 基线对比：`runs/results/c4_candidates_baseline_vs_optimized.csv`
- 对比说明：`runs/results/c4_candidates_baseline_vs_optimized.md`

最新一次 Q039/Q048 过强规则尝试已经本地备份到：

- `archive/experiment_runs/c4_latest_attempt_before_rollback_2026-06-02/`

该尝试不进入当前正式实验口径，后续只作为“prompt 过度优化可能导致收益不稳定”的边界案例。

### 11.2 本轮 C4 已完成的优化

C4 当前版本主要完成了以下工程和评测增强：

1. 补充结构化工具调用日志字段，能够记录真实调用的工具、调用次数、成功次数、工具选择匹配情况和工具输出是否被答案使用。
2. 将工具输出 ID 纳入最终引用，使文件读取、表格分析、计算器和代码执行结果可以被 AI Judge 和人工标注追踪。
3. 改进 C4 执行提示，明确 CSV/TSV 优先使用表格分析工具，计算题优先使用计算器，代码执行题优先使用代码执行或沙箱工具，缺文件任务必须保守回答。
4. 修正非文档类文件的 RAG 绑定范围，避免把 CSV、Python 文件简单当作普通文档问答材料处理。
5. 改进 AI Judge，使其能读取 C4 的工具输出和工具引用，不再只按文档 chunk citation 判断工具型任务。

### 11.3 当前 C4 初步结果

在 Q031-Q048 共 18 道 C4 候选题上，当前版本与初版对比如下：

| 指标 | C4 初版 | C4 当前采用版 |
| --- | ---: | ---: |
| 成功题数 | 18/18 | 18/18 |
| 程序级错误 | 0 | 0 |
| 平均延迟 | 16.36s | 18.30s |
| Answer Correctness | 0.778 | 0.833 |
| Citation Accuracy | 0.028 | 0.917 |
| Faithfulness | 0.306 | 0.972 |
| AI Judge 综合分 | 0.479 | 0.903 |
| Tool Selection Match | 未稳定记录 | 16/18 |
| Tool Output Used | 未稳定记录 | 17/18 |
| 平均 Tool Call Success Rate | 未稳定记录 | 0.851 |

从结果看，C4 当前版本的主要提升不是“多调用工具”，而是让工具调用过程变得可追踪、可引用、可评分。Citation Accuracy 和 Faithfulness 的提升主要来自工具输出 ID 与答案引用绑定，而不是单纯模型回答能力提升。

### 11.4 当前仍需注意的问题

C4 当前结果可以作为初步正式结果，但还不能直接冻结为最终结论，原因如下：

1. Q039 属于代码分析边界题，当前仍容易混淆“数据获取方式”和“本地保存/输出方式”。继续用 prompt 强行修复不稳定，更适合后续引入确定性的 AST 或正则扫描。
2. Q044 是缺文件保守回答题，工具选择匹配可能显示为不完全匹配，但答案如果明确说明文件不存在并拒绝编造，应按“预期失败处理正确”复核。
3. Q048 属于代码执行/表格排序混合题，部分运行会依赖表格预览而不是完整 CSV 读取，后续应加强 code_runner 对 CSV 文件的真实挂载和读取。
4. 当前 AI Judge 只能作为辅助，Q039、Q044、Q048 必须由唐宁做人工复核，不能只看自动分数。

### 11.5 下一步安排

- 赵启行：把 C4 当前结果写成“初步正式结果”，报告中说明当前采用版、回退尝试、边界题和后续优化方向。
- 唐宁：优先人工复核 Q039、Q044、Q048，再补全 C4 候选题的 Tool Selection、Tool Call Success、Tool Output Used 标注。
- 李金航：检查 C4 tool trace 字段是否稳定覆盖文件读取、表格分析、计算器和代码执行四类工具。
- 后续优化方向：不要继续堆 prompt；Q039 优先考虑 AST/regex 静态分析，Q048 优先考虑 code_runner 对 CSV 的完整读取，Q044 明确纳入缺文件保守回答测试。

当前判断：C4 可以继续推进人工复核和报告整理，但暂不建议宣布最终冻结。
