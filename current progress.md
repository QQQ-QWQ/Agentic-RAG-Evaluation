# Topic4 Agentic RAG Evaluation 当前进度

更新日期：2026-05-19  
当前主线：面向学习与知识服务任务的 Agentic RAG 技术增强与评测研究。

本项目不是做完整学习助手产品，而是搭建一个可复现实验工程：在同一知识库、同一测试集和可追踪日志下，对比 C0-C4 不同 RAG / Agentic RAG 配置，分析 query rewrite、hybrid retrieval、rerank、context expansion、planning、多轮检索、self-check 和工具调用等模块是否真正提升效果，以及带来多少延迟和 token 成本。

## 1. 当前阶段判断

当前项目处于：

```text
C2 主结论整理与冻结 + C3 小批量人工复核 + 测试集扩充准备阶段
```

当前不是继续堆功能的阶段，而是把已有实验结果变成可写入报告的研究结论。重点包括：

1. 冻结 C0/C1 作为阶段性基线。
2. 将 C2 主结论收敛到 Stage2：hybrid retrieval + rerank。
3. 将 C2 Stage3 selective context expansion 作为探索性优化，等待人工评分。
4. 对 C3 Q021-Q030 smoke test 做人工复核，判断 C3 是否可以进入正式批量实验。
5. 准备扩充测试集和后续公共 Benchmark / Dify / RAGFlow 横向参考。

当前代码状态：

```text
main 最新提交：36271d8 fix: repair c3 orchestration entry and document smoke test
本地 main 已与 origin/main 对齐
C2 selective context expansion 优化已推送
C3 orchestration 修复与实验说明已推送
```

## 2. 模块总览

| 模块 | 当前状态 | 是否可冻结 | 当前判断 |
| --- | --- | --- | --- |
| C0 Naive RAG | 已完成 20 题批量实验和人工评分初稿 | 可以阶段性冻结 | 普通 RAG baseline |
| C1 Query Rewrite RAG | 已完成优化版 C1 实验和人工评分初稿 | 可以阶段性冻结 | 提高文档命中，但答案质量未稳定提升，成本增加 |
| C2 Stage1 Hybrid | 已完成实验和人工评分 | 可作为 C2 消融对照 | 召回有收益，但质量不如 Stage2 |
| C2 Stage2 Hybrid + Rerank | 已完成实验和人工评分 | 建议作为 C2 主结论冻结 | 当前 C2 最稳定配置 |
| C2 Stage3 Context Expansion | 旧版评分差，新版 selective 已重跑 | 暂不冻结 | 新版需人工评分后再判断 |
| C3 Agentic Retrieval | 已完成 Q021-Q030 smoke test | 暂不冻结 | 链路跑通，但需人工评分与正式脚本 |
| C4 Tool-Augmented Agentic RAG | 尚未正式进入主线 | 不冻结 | 等 C3 稳定后再做 |
| Benchmark / Dify / RAGFlow | 尚未开始 | 不冻结 | 建议在 C3 主流程稳定后启动 |

## 3. 数据、知识库和测试集状态

当前知识库：

| 项目 | 数量 | 说明 |
| --- | ---: | --- |
| 文档记录 | 23 | 来自 `data/processed/documents.csv` |
| chunk 数量 | 475 | 来自 `data/processed/chunks.jsonl` |
| 核心回归测试题 | 20 | `data/testset/questions.csv`，Q001-Q020 |
| 核心参考答案 | 20 | `data/testset/references.csv`，evidence_chunk_id 已补齐 |
| C3 候选题 | 10 | `data/testset/questions_c3_candidates.csv`，Q021-Q030 |
| C3 候选参考 | 10 | `data/testset/references_c3_candidates.csv` |

当前知识库特点：

- 已能支撑 C0/C1/C2 的核心回归实验。
- 已能支撑 C3 小批量 planning / 多轮检索验证。
- 仍然偏小，后续最终实验需要扩展到 45-50 条自建测试题。
- 后续还需要加入 10-15 条公共 Benchmark 参考样例。
- `runs/` 下的日志和结果默认不提交 Git，需要本地复现或单独打包给组员。

额外材料：

```text
E:\Agentic RAG\知识库文档_纯净版_20260519_000421
E:\Agentic RAG\知识库文档_纯净版_20260519_000421.zip
```

该压缩包是当前知识库原始文档的纯净导出版本，便于成员区分哪些资料是真正用于知识库的材料。

### 3.1 实验环境与索引口径

当前 C0/C1/C2 的实验结论不能写成“基于 Chroma 向量数据库”。更准确的口径是：

```text
本阶段实验采用自实现轻量内存向量索引 SimpleVectorIndex 进行可控 RAG 对比；
Chroma 仅作为本地向量持久化缓存，用于减少重复 embedding，不作为本阶段核心检索引擎和实验变量。
```

当前实际实现：

| 项目 | 当前实现 |
| --- | --- |
| 核心索引方式 | `SimpleVectorIndex` 轻量内存向量索引 |
| dense 检索相似度 | Cosine similarity，即 `cosine_sim` |
| C0/C1 正式 top-k | `top_k=5` |
| 文档切块 | 默认 `chunk_size=500`、`overlap=80` |
| embedding 模型 | 火山方舟 Ark embedding，当前配置为 `doubao-embedding-vision-250615` |
| embedding 缓存 | 历史上使用 `.kb_embedding_cache.pkl`；当前工程可迁移或写入 Chroma 持久化缓存 |
| Chroma 当前作用 | 本地持久化缓存与索引还原，不作为本阶段核心检索效果来源 |
| C2 hybrid | Dense cosine + BM25，默认 `dense_weight=0.6`、`bm25_weight=0.4` |
| C2 rerank | LLM rerank，默认 `rerank_pool_size=20`，最终保留 `top_k=5` |

因此，后续报告应统一写成“基于自实现轻量内存向量索引的 RAG 对比实验”。如果最终正式方案要写“使用 Chroma 向量数据库”，需要在相同知识库、相同测试集、相同 embedding 模型、相同 top-k 和相同生成模型条件下，用 Chroma 查询机制复跑关键指标。

## 4. C0/C1 当前结论

C0/C1 均基于同一知识库和同一批 Q001-Q020 测试题。

### 4.1 自动指标

| 配置 | 题数 | 错误数 | 文档级命中 | 未命中题目 | 平均延迟 | 平均 token |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| C0 Naive RAG | 20 | 0 | 17/20 | Q005、Q007、Q013 | 7382 ms | 962 |
| C1 Query Rewrite RAG | 20 | 0 | 19/20 | Q013 | 37060 ms | 1905 |

### 4.2 人工评分初稿

| 配置 | Answer Correctness | Citation Accuracy |
| --- | ---: | ---: |
| C0 Naive RAG | 0.525 | 0.650 |
| C1 Query Rewrite RAG | 0.400 | 0.550 |

### 4.3 阶段结论

1. C1 相比 C0 提高了文档级命中率，从 17/20 提升到 19/20。
2. C1 没有稳定提升答案正确性和引用准确性，人工评分初稿反而低于 C0。
3. Query rewrite 对模糊、口语化、非规范查询有帮助，但存在改写漂移风险。
4. C1 的延迟和 token 成本明显高于 C0，后续报告中不能简单写“C1 优于 C0”。
5. C0/C1 现在可以作为阶段性冻结基线，用于后续 C2/C3 对照。

## 5. C2 当前结论

C2 目前已经完成正式复现、日志修复、人工评分和 Stage3 优化复测。

### 5.1 C2 三阶段定义

| 阶段 | 配置 | 目的 |
| --- | --- | --- |
| Stage1 | C1 + hybrid retrieval | 验证 dense retrieval + BM25 混合检索是否提升召回 |
| Stage2 | C1 + hybrid retrieval + rerank | 验证 rerank 是否提升排序、答案质量和引用准确性 |
| Stage3 | C1 + hybrid retrieval + rerank + context expansion | 验证上下文扩展是否能补充邻近证据 |

### 5.2 C2 人工评分结果

| 配置 | 题数 | Answer Correctness | Citation Accuracy | 当前判断 |
| --- | ---: | ---: | ---: | --- |
| C2 Stage1：Hybrid Retrieval | 20 | 0.600 | 0.625 | 可作为 C2 消融对照 |
| C2 Stage2：Hybrid Retrieval + Rerank | 20 | 0.800 | 0.800 | 建议作为 C2 主结论冻结 |
| C2 Stage3：旧版固定 Context Expansion | 20 | 0.150 | 0.200 | 不建议作为正向结论 |

结论：C2 Stage2 是目前最稳定、最适合写进报告的 C2 版本。Rerank 的收益清楚；旧版固定 context expansion 引入大量噪声，不能作为有效模块结论。

### 5.3 C2 Stage3 selective context expansion 优化

旧版 Stage3 的问题是：固定扩展相邻 chunk，容易把无关上下文塞进 prompt，导致答案拒答、引用混乱、token 成本升高。

优化后规则：

1. 只对 `multi_doc`、`fuzzy_query`、`insufficient_evidence` 等需要补证据的题型启用。
2. 不对 `simple_qa`、`calculation`、`code_execution` 等题型启用。
3. 只扩展 rank <= 3 的命中 chunk。
4. 只扩展同一 `doc_id` 下相邻 chunk。
5. 遇到新标题边界停止扩展。
6. 限制扩展数量和总上下文字符数。
7. 保留 citation 的原始 chunk_id，同时在日志记录 `expanded_chunk_ids`。
8. 没有触发扩展时，Stage3 输出应接近 Stage2。

优化后 Stage3 自动指标：

| 配置 | 题数 | 错误数 | 文档级命中 | Gold chunk 命中 | 平均延迟 | 平均 token |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| C2 Stage3 selective context expansion | 20 | 0 | 19/20 | 15/20 | 37056.8 ms | 13352.0 |

当前判断：新版 Stage3 已经比旧版设计更合理，但只有自动指标，缺少人工评分。因此它暂时只能作为探索性优化，不能替代 Stage2 作为 C2 主结论。

### 5.4 C2 当前应冻结什么

建议冻结：

```text
C2 主结论 = Stage2：hybrid retrieval + rerank
```

不要冻结为主结论：

```text
旧版 Stage3 context expansion
新版 Stage3 selective context expansion
```

Stage3 可以写入报告中的“失败案例与优化尝试”或“收益边界分析”，但不应写成 C2 的最终最优配置。

## 6. C3 当前进展

C3 目标是验证 Agentic Retrieval：任务规划、多轮检索、query planning、self-check 等能力。当前 C3 尚未进入正式批量实验，只完成了 Q021-Q030 小批量 smoke test。

### 6.1 C3 已完成工作

已完成：

- 修复 `OrchestrationConfig` 缺少 `enable_c4_tools` 字段的问题。
- 修复 C3 编排层构建 Agent 和第二层消息时无法传递该字段的问题。
- 使用 `main.py agent --c3 --planning-rewrite --json --once` 跑通 Q021-Q030。
- 生成本地 C3 运行输出：
  - `runs/results/c3_smoke_results.csv`
  - `runs/logs/c3_agentic_retrieval/run_logs.jsonl`
  - `runs/logs/c3_agentic_retrieval/Q021_console.txt` 到 `Q030_console.txt`
  - `runs/logs/c3_agentic_retrieval/summary.json`
- 新增 `docs/c3_smoke_experiment_guide.md`，说明运行方式、结果摘要和人工复核要求。

注意：以上 `runs/` 输出默认被 Git 忽略，已经在本地生成，但不会通过 GitHub 自动同步给其他成员。

### 6.2 C3 smoke test 自动结果

| 指标 | 结果 |
| --- | ---: |
| 测试题数 | 10 |
| 程序级错误 | 0 |
| RAG 调用成功 | 10/10 |
| 多查询或多 pipeline 行为 | 10/10 |
| 平均延迟 | 152038.1 ms |
| 平均 gold doc 覆盖 | 0.9000 |
| 平均 gold chunk 覆盖 | 0.6067 |

逐题覆盖情况：

| 题号 | 题型 | Gold doc 覆盖 | Gold chunk 覆盖 | 延迟 ms |
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

### 6.3 C3 当前判断

1. C3 链路已经能跑通，程序级 0 error。
2. 每题都触发了 RAG 调用，并且能看到多查询或多 pipeline 行为。
3. 平均 gold doc 覆盖较高，说明文档层面证据基本能找到。
4. 平均 gold chunk 覆盖只有 0.6067，复杂题证据定位仍不稳定。
5. 平均延迟超过 150 秒，成本问题非常明显。
6. Q021、Q025、Q027 是当前重点失败/弱覆盖题。
7. C3 目前只能算 smoke test 通过，不能作为正式 C3 结论。

### 6.4 C3 下一步

C3 下一步不是直接扩大功能，而是完成复核和正式化：

1. 唐宁建立 `manual_eval_c3_smoke.csv`，人工评分 Q021-Q030。
2. 评分字段至少包括：
   - `question_id`
   - `answer_correctness`
   - `citation_accuracy`
   - `planning_quality`
   - `retrieval_sufficiency`
   - `main_problem`
   - `comment`
   - `reviewer`
   - `status`
3. 李金航解释 C3 中多查询、多 pipeline、planning 行为是否符合预期。
4. 赵启行根据人工评分判断 C3 是否进入正式批量实验。
5. 后续补一个 C3 正式批量脚本，使输出格式和 C0/C1/C2 一致。

## 7. C4 当前状态

C4 尚未正式进入主线。

C4 预期内容：

- 文件读取工具
- 代码执行工具
- 计算器工具
- 表格分析工具

当前不建议马上开始 C4，原因：

1. C3 的 planning 和多轮检索还没有冻结。
2. C3 延迟和证据覆盖问题尚未解决。
3. 如果现在直接进入 C4，后续很难区分“工具调用收益”和“C3 检索/规划收益”。
4. C4 至少需要额外的工具型测试题和工具调用日志规范。

建议顺序：

```text
C2 Stage2 冻结 -> C3 smoke 人工复核 -> C3 正式批量脚本 -> C3 阶段结论 -> C4 工具调用
```

## 8. 当前重点文档

| 文档 | 用途 |
| --- | --- |
| `README.md` | 项目总说明和快速入口 |
| `current progress.md` | 当前详细进度说明 |
| `docs/README.md` | docs 目录导航 |
| `docs/interface_and_logging_rules.md` | C0/C1/C2 输入输出结构和日志字段 |
| `docs/batch_experiment_guide.md` | C0/C1 批量实验说明 |
| `docs/c2_ablation_guide.md` | C2 三阶段消融实验说明 |
| `docs/c3_smoke_experiment_guide.md` | C3 小批量 smoke test 说明 |
| `docs/evaluation_plan.md` | 人工评测流程和评分规则 |
| `docs/failure_cases.md` | 失败案例记录 |
| `docs/manual_eval_c0_c1_summary.md` | C0/C1 人工评测摘要 |
| `docs/evaluation_ai_judge.md` | AI Judge 辅助评测说明 |
| `docs/experiment_notes.md` | 实验记录 |

外部材料目录中另有：

```text
E:\Agentic RAG\开题报告与开发材料\member_b_data_evaluation_tasks.md
```

该文档已经详细说明当前三人分工，尤其是唐宁在 C2/C3 人工评测中的任务。

## 9. 每个人当前应该做什么

### 9.1 赵启行

当前职责：组长、研究主线、结论和协作节奏负责人。

近期任务：

1. 将 C2 主结论冻结到 Stage2，不把 Stage3 写成最优配置。
2. 整理 C0/C1/C2/C3 的阶段表格：检索、答案、引用、延迟、token。
3. 给唐宁提供 C3 本地 `runs/` 输出，或指导她本地复现 C3 smoke test。
4. 检查每次提交范围，避免把 `.env`、`runs/`、`archive/`、压缩包和无关大文件推到仓库。
5. 组织测试集扩充，但不要在 C3 未复核前盲目扩太大。
6. 准备最终报告中的“收益边界”和“失败案例分析”口径。

### 9.2 唐宁

当前职责：数据与评测负责人。当前阶段最关键任务是把实验输出变成可信评价。

近期任务：

1. 复核 C2 `manual_eval_c2.csv`，确认 Stage2 的 0.800 / 0.800 是否合理。
2. 为新版 C2 Stage3 selective context expansion 建立人工评分表。
3. 建立 C3 `manual_eval_c3_smoke.csv`，对 Q021-Q030 做人工评分。
4. 对每题判断：答案是否正确、引用是否支撑答案、规划是否合理、证据是否充分。
5. 重点检查 Q021、Q025、Q027、Q029、Q030。
6. 整理失败原因标签，例如 `wrong_citation`、`missing_evidence`、`planning_failure`、`context_noise`、`latency_too_high`。
7. 后续准备扩充测试题，不追求数量，先保证每题有明确 gold doc / gold chunk 和评分标准。

### 9.3 李金航

当前职责：工程实现、复现和模块解释负责人。

近期任务：

1. 解释 C2 Stage1、Stage2、Stage3 的技术差异和成本差异。
2. 说明为什么 Stage2 效果最好，为什么旧版 Stage3 失败。
3. 配合检查新版 Stage3 selective context expansion 是否按条件触发。
4. 检查 C3 planning、多查询、多 pipeline 行为是否符合预期。
5. 后续准备 C3 正式批量脚本，使输出结构对齐 C0/C1/C2。
6. 在进入 C4 前，先确认 C3 的核心日志字段和结果 CSV 字段。

## 10. 下一步执行顺序

优先级从高到低：

1. 唐宁完成 C3 smoke test 人工评分。
2. 唐宁完成新版 C2 Stage3 selective 人工评分。
3. 赵启行汇总 C2 Stage2 冻结结论，并将 Stage3 定位为探索性优化。
4. 李金航解释 C2/C3 的关键工程行为和失败原因。
5. 三人共同确定 C3 是否值得进入正式批量实验。
6. 补 C3 正式批量脚本，输出 CSV 和 JSONL 日志。
7. 扩充测试集到 45-50 条，其中要覆盖 simple_qa、fuzzy_query、multi_doc、insufficient_evidence、tool-like task 等类型。
8. C3 稳定后再启动 C4 工具调用。
9. 公共 Benchmark 子集和 Dify / RAGFlow 横向参考建议在 C3 主流程稳定后开始。

## 11. 当前主要风险

1. **只看文档命中率会误判效果。**  
   C1 就是典型例子：文档命中提高，但人工答案质量没有提高。

2. **Stage3 容易引入上下文噪声。**  
   旧版 Stage3 已经证明固定扩展风险很高，新版 selective 也必须经过人工评分。

3. **C3 延迟过高。**  
   当前平均延迟超过 150 秒，后续如果要写成正式方案，必须解释成本是否可接受，以及哪些任务才值得使用 C3。

4. **测试集规模仍偏小。**  
   20 条核心题适合作为回归集，不能支撑最终完整结论。C3 的 10 条候选题也只能做 smoke test。

5. **`runs/` 不进 Git。**  
   实验结果和日志默认被 `.gitignore` 忽略。组员拉仓库不会自动得到本地实验输出，需要单独打包或自己复现。

6. **C4 不宜提前启动。**  
   C3 未验收前直接做 C4，会让变量混在一起，最后无法说明效果来自 planning、多轮检索，还是工具调用。

7. **Chroma 口径需要统一。**  
   当前核心实验应归因于 `SimpleVectorIndex`、query rewrite、hybrid retrieval、rerank 和 context expansion 等模块；Chroma 只能写作缓存或持久化机制。若把 Chroma 写成正式向量数据库方案，必须复跑关键指标。

## 12. 当前总判断

当前项目主线是清楚的：

```text
C0/C1 作为阶段性基线 -> C2 Stage2 作为当前最稳增强结论 -> C3 已跑通但需人工复核 -> C4 暂缓
```

最可靠的阶段结论是：

```text
Hybrid retrieval + rerank 是当前最稳定的 C2 增强方案。
```

最需要补齐的是：

```text
C3 人工评分、C2 Stage3 selective 人工评分、失败案例归因、测试集扩充。
```

后续所有工作都应围绕一个核心问题展开：Agentic RAG 的额外规划、检索、验证和工具调用，是否真的在复杂知识服务任务中带来足够收益，并且其延迟和 token 成本是否可以接受。
