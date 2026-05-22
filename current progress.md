# Topic4 Agentic RAG Evaluation 当前进度

更新日期：2026-05-23
当前主线：面向学习与知识服务任务的 Agentic RAG 技术增强与评测研究。
文档职责：根目录 `README.md` 只保留开题报告正文与参考文献；本文件集中维护仓库运行方式、当前进度、阶段结论和下一步任务；`docs/` 保存长期规范、架构、实验记录和专题说明。

## 1. 当前阶段判断

当前项目处于：

```text
C2 主结论收尾 + C3/C4 批量评测准备 + 测试集扩充准备阶段
```

当前不是继续堆功能的阶段。主要工作应从“代码能跑”转为“结果可信”：补齐 C3/C4 批量日志、人工评分、失败案例和成本分析。

| 模块 | 当前状态 | 阶段判断 |
| --- | --- | --- |
| C0 Naive RAG | 20 题批量与人评已完成 | 可阶段性冻结 |
| C1 Query Rewrite RAG | 优化版 C1 已跑完 20 题 | 可阶段性冻结，但不能简单宣称优于 C0 |
| C2 Stage1 Hybrid | 已完成复现与人评 | 可作为消融对照 |
| C2 Stage2 Hybrid + Rerank | 已完成复现与人评 | 当前 C2 主结论，应优先冻结 |
| C2 Stage3 Context Expansion | 固定扩展淘汰，选择性扩展保留 | 作为收益边界和失败案例分析，不作为主增益点 |
| AI Judge | 多维评分脚本与 Prompt 已接入 | 只作为辅助评测，不替代人工评分 |
| C3 Agentic Retrieval | 工程链路与 smoke 入口已通 | 需复跑最新 batch 并人工评分 |
| C4 Tool-Augmented Agentic RAG | 工具链路与 batch 入口已通 | 需跑工具题 batch、补工具调用评分 |
| Benchmark / Dify / RAGFlow | 未开始 | 暂缓，等 C3/C4 主线稳定后做参考对比 |

## 2. 仓库运行入口

### 2.1 环境准备

复制 `.env.example` 为 `.env` 并填写必要 Key：

```text
ARK_API_KEY=your_key_here
DEEPSEEK_API_KEY=your_key_here
```

C4 网页、沙箱、写盘和 shell 可选：

```text
FIRECRAWL_API_KEY=...
SANDBOX_ENABLED=true
SANDBOX_TIMEOUT_SEC=60
FILE_WRITE_ENABLED=true
SHELL_COMMAND_ENABLED=true
SHELL_TIMEOUT_SEC=60
```

安装依赖：

```powershell
uv sync
uv sync --group agent
uv run python main.py kb sync
```

注意：`.env`、`.venv/`、`runs/`、`archive/`、本地大体积索引和 API Key 不提交仓库。

### 2.2 常用命令

| 任务 | 命令 |
| --- | --- |
| 集成工作台 | `uv run python main.py` |
| C3/C4 网页 Demo | `uv run python main.py client` |
| C3 仅检索 | `uv run python main.py client --c3` |
| C4 工具 + 沙箱 | `uv run python main.py client --c4 --sandbox` |
| 终端 C4 对话 | `uv run python main.py client --console --c4` |
| 查看日志与继续命令 | `uv run python main.py logs` |
| C0/C1 批量 | `uv run python main.py experiment batch` |
| C2 消融 | `uv run python main.py experiment c2 --phase all --limit 20` |
| C3 smoke 批量 | `uv run python run_c34_batch_eval.py --tier c3 --split c3_smoke --verbose-events` |
| C4 工具题批量 | `uv run python run_c34_batch_eval.py --tier c4 --split c4_tools --sandbox --verbose-events` |
| 全量测试 | `uv run pytest` |
| 代码检查 | `uv run ruff check .` |

## 3. 代码仓库结构

```text
topic4-ARAG-eval/
├── README.md                  # 开题报告正文与参考文献，不再放运行进度
├── current progress.md        # 当前进度、运行入口、下一步计划
├── main.py                    # 统一 CLI 入口
├── run_batch_experiments.py   # C0/C1 批量实验
├── run_c2_retrieval_ablation.py
├── run_c34_batch_eval.py      # C3/C4 批量评测
├── run_score_rag_multidim.py  # 多维 AI Judge 辅助评分
├── configs/                   # C0-C4 与消融配置
├── prompts/                   # Query rewrite、self-check、judge 等 Prompt
├── data/                      # raw / processed / testset
├── src/agentic_rag/           # 项目核心代码
├── docs/                      # 架构、规范、实验记录与专题文档
├── tests/                     # 单元测试
├── runs/                      # 本地实验输出，默认不提交
└── archive/                   # 本地备份，默认不提交
```

核心代码结构：

| 目录 | 作用 |
| --- | --- |
| `src/agentic_rag/documents/` | 文档解析、会话文档、传入文件检查 |
| `src/agentic_rag/rag/` | 分块、向量索引、Chroma 持久化、上下文扩展 |
| `src/agentic_rag/pipelines/` | C0-C2 本地 RAG 编排 |
| `src/agentic_rag/experiment/` | C0-C4 批量实验、知识库同步、C3/C4 batch |
| `src/agentic_rag/deep_planning/` | L1 规划、L2 Deep Agent、工具注册 |
| `src/agentic_rag/orchestration/` | L1/L2/L3 编排循环、研判与重试 |
| `src/agentic_rag/tools/` | C4 文件、计算器、表格、代码、网页、shell 工具 |
| `src/agentic_rag/telemetry/` | 会话审计、trace、chat transcript |
| `src/agentic_rag/evaluation/` | 人工/AI Judge 辅助评分 |

## 4. 数据、知识库和测试集状态

| 项目 | 当前状态 |
| --- | --- |
| 主测试集 | `data/testset/questions.csv`，Q001-Q020 |
| 主参考答案 | `data/testset/references.csv` |
| C3 候选题 | `data/testset/questions_c3_candidates.csv`，Q021-Q030 |
| C3 候选参考 | `data/testset/references_c3_candidates.csv` |
| 人工评分 | `manual_eval_c0_c1.csv`、`manual_eval_c2.csv` |
| C3/C4 人工评分 | 待补 |
| 最终目标 | 自建测试集扩至 40-50 题，另补 10-15 条 Benchmark 参考样例 |

当前索引口径：

```text
C0/C1/C2 结论主要归因于自实现轻量检索、query rewrite、hybrid retrieval、rerank 和 context expansion 等模块。
Chroma 当前主要用于全库持久化和缓存；若最终报告写“基于 Chroma 向量数据库”，需在同一知识库、测试集、embedding 和模型条件下复跑关键指标。
```

## 5. C0/C1 当前结论

| 配置 | 文档级命中 | 人工 Answer Correctness | 人工 Citation Accuracy | 判断 |
| --- | ---: | ---: | ---: | --- |
| C0 Naive RAG | 17/20 | 0.525 | 0.650 | 基线可冻结 |
| C1 Query Rewrite RAG | 19/20 | 0.400 | 0.550 | 改善召回，但答案质量未稳定提升 |

结论：C1 对模糊、口语化查询有帮助，但存在改写漂移和成本增加。报告中应写“C1 改善检索召回，但不必然改善最终答案”。

## 6. C2 当前结论

| 阶段 | 新增能力 | 人工 Answer Correctness | 人工 Citation Accuracy | 判断 |
| --- | --- | ---: | ---: | --- |
| Stage1 | Hybrid retrieval | 0.600 | 0.625 | 召回有收益，但证据排序不够稳定 |
| Stage2 | Hybrid retrieval + rerank | 0.800 | 0.800 | 当前 C2 主结论 |
| 旧 Stage3 | 固定 context expansion | 0.150 | 0.200 | 已淘汰 |
| 新 Stage3 | 选择性 context expansion | 待人工评分 | 待人工评分 | 作为边界分析，不替代 Stage2 |

Stage3 最新保留规则：

- 只对 `multi_doc`、`fuzzy_query`、`insufficient_evidence` 等题型考虑扩展。
- 不对 `simple_qa`、`calculation`、`code_execution`、`table_analysis` 题型扩展。
- 只扩展排名靠前、同文档、同小节内的相邻 chunk。
- 使用上下文预算限制。
- 日志区分 `retrieved_chunk_ids`、`expanded_chunk_ids`、`final_citation_chunk_ids`。
- 舍弃 keyword filter 版本。

C2 最终口径：

```text
Hybrid retrieval + rerank 是当前最稳定的 C2 增强方案；context expansion 有探索价值，但在当前测试集上收益不稳定，适合写入边界分析和失败案例。
```

## 7. C3 当前状态与下一步

C3 定位：Agentic Retrieval RAG，即在 C2 基础上加入任务规划、查询拆解、多轮 RAG 检索、多 pipeline 选择和初步证据检查。

已完成：

- `main.py client --c3` / `main.py agent --c3` 链路可运行。
- `run_c34_batch_eval.py --tier c3 --split c3_smoke` 批量入口已存在。
- 旧 smoke 结果显示 Q021-Q030 可跑通，RAG 调用 10/10，多查询/多 pipeline 行为 10/10。
- 平均延迟约 152 秒，gold doc 覆盖较高，但 gold chunk 覆盖约 60.67%，证据精确定位仍不稳。

C3 下一步必须按顺序做：

1. 复跑最新 C3 smoke batch：

```powershell
uv sync --group agent
uv run python main.py kb sync
$env:PYTHONUTF8="1"
uv run python run_c34_batch_eval.py --tier c3 --split c3_smoke --verbose-events
```

2. 检查输出：

```text
runs/logs/c3_agentic_retrieval_batch/run_logs.jsonl
runs/logs/c3_agentic_retrieval_batch/batch_report.json
```

3. 建立人工评分文件：

```text
data/testset/manual_eval_c3_smoke.csv
```

建议字段：

```csv
question_id,answer_correctness,citation_accuracy,planning_quality,retrieval_sufficiency,main_problem,comment,reviewer,status
```

4. 根据人工评分决定是否优化：

| 问题 | 优化方向 |
| --- | --- |
| 子查询过多、延迟过高 | 限制 planner 最多 2-3 个子查询 |
| 多 pipeline 没有带来增益 | 默认优先使用 C2 Stage2 rerank，减少 Stage3 |
| 引用不准 | 增加证据合并、去重和最终引用过滤 |
| 过度拒答 | 调整 self-check，只检查证据是否足够支撑核心结论 |

C3 目前验收标准建议：程序错误为 0；gold doc 覆盖不低于 90%；gold chunk 覆盖尽量提升到 70%；平均延迟尽量压到 90 秒以内；必须有人评 Answer Correctness 和 Citation Accuracy。

## 8. C4 当前状态与下一步

C4 定位：Tool-Augmented Agentic RAG，即在 C3 上加入外部工具调用，重点验证工具是否提升工具型任务完成率。

已完成：

| 工具 | 实现 |
| --- | --- |
| 文件读取 | `topic4_file_read` |
| 文件写入/编辑 | `topic4_file_write`、`topic4_file_edit`，主要用于 Demo 和工程内操作 |
| 文件入库 | `topic4_file_ingest` |
| 计算器 | `topic4_calculator` |
| 表格分析 | `topic4_table_analyzer` |
| 代码执行 | `topic4_code_runner`，本地子进程沙箱 |
| 受限 shell | `topic4_shell_exec`，主要用于 Demo 和工程内命令 |
| 网页抓取 | Firecrawl，可选，需要 API Key |

C4 下一步必须先跑工具题 batch：

```powershell
uv sync --group agent
uv run python main.py kb sync
$env:PYTHONUTF8="1"
uv run python run_c34_batch_eval.py --tier c4 --split c4_tools --sandbox --verbose-events
```

检查输出：

```text
runs/logs/c4_tool_augmented_batch/run_logs.jsonl
runs/logs/c4_tool_augmented_batch/batch_report.json
```

C4 人工评分字段建议：

```csv
question_id,required_tool,selected_tools,tool_selection_accuracy,tool_call_success,tool_result_used,task_completion,answer_correctness,citation_accuracy,main_problem,comment,reviewer,status
```

C4 当前工具题只有 Q013、Q016-Q019，数量偏少。建议扩到 12-15 题：

| 类型 | 数量建议 |
| --- | ---: |
| 文件读取 | 3 |
| 计算器 | 3 |
| 表格分析 | 3 |
| 代码执行 | 3 |
| 可选网页或 shell Demo | 1-3 |

注意：文件写入、shell、Firecrawl 可以作为现场 Demo 能力，不建议先放入主评测，避免安全、网络和复现问题影响主线结论。

## 9. docs 文档整理口径

`docs/` 文档按以下职责维护：

| 类别 | 主文档 | 说明 |
| --- | --- | --- |
| 文档导航 | `docs/README.md` | docs 目录入口，说明哪些文档还在维护 |
| 协作规范 | `environment_and_git_rules.md`、`collaboration_workflow.md`、`directory_rules.md` | 环境、Git、分工和目录规则 |
| 架构说明 | `ARCHITECTURE.md`、`agent_runtime_architecture.md`、`c0_baseline_architecture.md` | 总架构、Runtime、C0 历史基线 |
| 实验指南 | `batch_experiment_guide.md`、`c2_ablation_guide.md`、`c3_smoke_experiment_guide.md` | C0/C1、C2、C3 的可复现运行说明 |
| 评测规范 | `evaluation_plan.md`、`evaluation_ai_judge.md` | 人工评分和 AI Judge 辅助评分 |
| 实验记录 | `experiment_notes.md` | 按时间记录每次实验，不替代正式结论 |
| 专题报告 | `c2_three_layer_retrieval_report.md`、`manual_eval_c0_c1_summary.md`、`failure_cases.md` | 阶段性总结和失败案例 |

已合并或不再单独维护：

- `team_roles.md` 已合并到 `collaboration_workflow.md`。
- 根目录 `README.md` 的运行进度内容移入 `current progress.md`。
- 后续不再把同一类运行命令同时写进 README、docs/README 和多个指南，优先维护 `current progress.md` 与对应实验指南。

## 10. 成员当前任务

| 成员 | 当前重点 |
| --- | --- |
| 赵启行 | 收口 C2 结论；组织 C3/C4 batch；控制实验变量；汇总报告口径 |
| 唐宁 | 补 C2 Stage3 selective 人工评分；补 C3/C4 人工评分；扩充测试集与 references |
| 李金航 | 跑 C3/C4 batch；解释 C3 planning 与 C4 工具调用链路；定位工程失败原因 |

## 11. 下一步执行顺序

优先级从高到低：

1. 复跑 C3 smoke batch，生成最新日志。
2. 复跑 C4 tools batch，生成工具调用日志。
3. 唐宁完成 C3/C4 人工评分。
4. 赵启行汇总 C0-C4 对比表和 C2 最终口径。
5. 扩充测试集到 40-50 题。
6. 整理至少 10 个失败案例。
7. 补 C4 消融：`no-tool`、`no-self-check`、`no-rewrite`。
8. 最后再做 Benchmark 子集和 Dify/RAGFlow 横向参考。

## 12. 当前主要风险

1. **C3/C4 缺正式 batch 和人评。** 工程能跑不等于实验完成。
2. **C3 延迟偏高。** 如果平均 150 秒级别，需要解释何种任务才值得走 C3。
3. **C4 工具题数量太少。** 5 道题不足以支撑工具有效性结论。
4. **Stage3 不能过度包装。** 选择性扩展只是可控性改善，不是 C2 主增益。
5. **`runs/` 不进 Git。** 组员拉仓库拿不到本地结果，需要自己复现或单独打包。
6. **Benchmark / Dify / RAGFlow 暂缓。** 当前主线还没闭环，过早做横向参考会分散精力。
