# C3-lite 优化方案与技术报告

更新日期：2026-05-27

## 1. 技术问题定位

当前 C3 的目标不是简单把 Agentic RAG 流程做得更复杂，而是在复杂知识任务中，以可接受的成本提升答案质量、引用可信度和证据完整性。

前期实验表明，旧版 C3 的主要问题不是“完全检索不到资料”，而是：

1. 子查询过多，导致延迟和 Token 成本过高。
2. 多轮检索结果重复，证据排序和去重不够稳定。
3. 检索到的 chunk 未经过有效证据筛选，容易把背景资料和直接证据混在一起。
4. 多对象题容易漏项，例如只回答部分框架、部分论文或部分方法。
5. claim 与 citation 绑定较弱，最终引用有时过宽或不直接支撑结论。
6. self-check 偏泛化，能指出“可能有问题”，但不能稳定给出具体修正动作。

因此，本轮 C3 优化的核心问题是：

```text
如何在不显著增加检索轮数和 LLM 调用成本的前提下，
提升 C3 对复杂知识任务的答案整合质量和引用准确性。
```

## 2. 优化目标

C3-lite 优化目标分为三类。

### 2.1 质量目标

- 提高多文档、多对象、模糊查询和证据不足类任务的答案正确性。
- 降低漏答 required items 的概率。
- 提高 citation 与 claim 的直接对应关系。
- 降低 unsupported claim 和过度拒答。

### 2.2 成本目标

- 控制 RAG 查询次数，避免所有问题都走重型 Agentic 流程。
- 避免新增独立 citation selector LLM 节点。
- 避免完整 parent-child indexing 重构。
- 避免把 self-check 设计成无限循环。

### 2.3 研究目标

- 使 C3 的收益来源可解释：多查询、RRF、证据筛选、答案结构化和 claim-level self-check 分别解决什么问题。
- 形成可复核的日志字段，支持后续人工评分和失败案例分析。
- 保留与 C2 Stage2 / C2 Stage3 的同题对照能力。

## 3. 总体技术路线

C3-lite 采用“轻量 Agentic Retrieval + 结构化证据整合”的路线。

整体流程为：

```text
用户问题
  -> planning rewrite
  -> task planning
  -> limited sub-queries
  -> C2 rerank pipeline / C3-lite RAG subagent
  -> multi-query RRF fusion
  -> Evidence Grader
  -> coverage checklist
  -> claim-first answer generation
  -> claim-level self-check
  -> final answer with citations
```

该路线借鉴 Self-RAG、CRAG 和 LangGraph RAG 中的思想：

- 先判断资料是否相关；
- 再基于证据生成答案；
- 最后检查答案是否被证据支撑。

但本项目不照搬完整框架，只保留低成本、可实现、可解释的部分。

## 4. 核心优化模块

### 4.1 查询预算与轻量化控制

旧版 C3 的一个主要问题是：简单题和复杂题都可能被拆成较多子查询，导致延迟显著增加。

优化策略：

- simple_qa：理论上不需要 C3，后续系统级方案可路由到 C2 Stage2。
- fuzzy_query：最多 2 个 RAG 查询。
- multi_doc：最多 3 个 RAG 查询。
- insufficient_evidence：最多 1 次补检索，总 RAG 查询不超过 2。
- calculation / table_analysis / code_execution：C3 不硬做，后续交给 C4。

当前 C3 实验中，为避免把 adaptive route 的收益误写成 C3 自身收益，正式对照时使用：

```text
--no-adaptive-route
```

因此，当前 C3-lite 的低成本主要来自 RAG 查询预算、重复查询抑制和更紧凑的证据处理，而不是把简单题路由给 C2。

### 4.2 多查询 RRF 融合

多查询检索的风险是结果重复、排序混乱、引用不稳。

优化策略：

```text
sub-query 1 -> top_k chunks
sub-query 2 -> top_k chunks
sub-query 3 -> top_k chunks
        -> chunk_id 去重
        -> RRF fusion
        -> rerank / top-k 截断
```

这样 C3 与 C2 的区别更加清楚：

- C2 Stage2：单查询 hybrid retrieval + rerank。
- C3-lite：多查询 retrieval + RRF fusion + evidence filtering + claim-level check。

RRF 的作用不是增加召回数量，而是让多查询结果在去重后形成更稳定的候选证据排序。

### 4.3 Evidence Grader

旧版 C3 容易把“背景相关 chunk”和“直接支撑结论的 chunk”一起交给答案生成，导致引用过宽或答案被噪声影响。

Evidence Grader 的目标是在答案生成前做轻量证据筛选。

输入：

```text
question
retrieved_chunks
task_type
```

输出字段：

```text
chunk_id
relevance
support_type: direct / partial / background / irrelevant
supported_claims
keep
```

保留规则：

- 默认保留 `direct` 和高相关 `partial`。
- `background` 仅在多文档总结任务中少量保留。
- `irrelevant` 不进入最终答案上下文。

注意：Evidence Grader 是 C3-lite 的证据筛选模块，不应直接加到 C2 Stage3 上。本轮已经将 C2 Stage3 回退为旧版口径，避免 Stage3 被 Evidence Grader 影响。

### 4.4 Required-items 覆盖清单

多对象题是 C3 的重点难点。例如：

- 比较 Self-RAG、CRAG、A-RAG。
- 比较 Dify、RAGFlow、CrewAI、LangGraph。
- 比较两篇论文的分类体系。

旧版答案生成容易只回答检索到的部分对象，造成漏项。

优化策略是在答案生成前要求第二层 Agent 先形成内部覆盖清单：

```text
required_item
supporting_chunk_id
support_status: supported / partial / missing
answer_point
```

最终答案必须逐项覆盖 required items：

- 有证据：正常回答并引用。
- 部分证据：说明有限支持。
- 缺证据：明确写“现有资料不足”，不能直接漏掉。

该清单不要求完整展示给用户，但最终答案必须遵守它。

### 4.5 Claim 与 Citation 绑定

旧版 C3 的引用问题主要有两类：

1. 引用过宽，把相关但不直接支撑结论的 chunk 也列入 citation。
2. claim 与 citation 不对应，导致 Citation Accuracy 下降。

优化策略：

- 最终答案采用 claim-first 风格。
- 每条核心 claim 后跟 1 个最直接 citation。
- 每条 claim 最多 1-2 个 citation。
- 背景 chunk、expanded context、泛相关 chunk 不进入最终引用。

引用数量软约束：

```text
simple / single-object: 1-3 个引用
multi_doc / comparison: 3-6 个引用
```

超出时优先删除背景引用，而不是删除核心结论。

### 4.6 Claim-level Self-check

旧版 self-check 的问题是“能判断但不一定能修正”。因此本轮将 self-check 从泛泛检查改为 claim-level 检查。

检查字段：

```text
support_verdict
unsupported_claims
missing_required_items
citation_mismatches
revision_instruction
```

三档判断：

- supported：核心结论均有证据，直接输出。
- partially_supported：保留可支持部分，修正缺口，不全盘拒答。
- unsupported：若仍有检索预算，允许一次补检索；否则保守回答资料不足。

修正动作必须具体：

- 删除某条 unsupported claim。
- 补充遗漏对象。
- 将某个对象改写为“资料不足”。
- 替换不匹配 citation。
- 缩短过宽引用列表。

## 5. C2 Stage3 回退说明

本轮同时对 C2 Stage3 做了代码口径回退。

原因：

- C2 Stage3 next 尝试把上下文扩展与 Evidence Grader 结合，但 30 题结果退化。
- 该方案综合分低于 C2 Stage2 和旧版 C2 Stage3。
- 因此不适合作为 C2 正式增强方案。

回退后 C2 Stage3 定义为：

```text
C2 Stage2 + context_neighbor_chunks=1
```

即：

- 保留 query rewrite；
- 保留 hybrid retrieval；
- 保留 rerank；
- 保留邻接 chunk 上下文扩展；
- 不启用 Evidence Grader；
- 不采用当前 next 版较小上下文预算。

后续报告口径：

- C2 Stage2 是稳定主基线。
- C2 Stage3 old 是上下文扩展边界对照。
- C2 Stage3 next 是失败优化尝试，只用于边界分析。

## 6. 接口与日志字段

为了支持后续评测和失败分析，C3-lite 需要保留以下字段。

### 6.1 检索与融合字段

```text
sub_queries
rag_query_count
retrieved_doc_ids
retrieved_chunk_ids
multi_query_fusion
rrf_input_count
rrf_output_chunk_ids
```

用途：

- 判断 C3 是否真的发生多查询。
- 判断 RRF 是否去重并稳定候选证据。
- 分析 RAG 调用是否过多。

### 6.2 Evidence Grader 字段

```text
evidence_grades
evidence_grader_kept_chunk_ids
kept_evidence_chunks
```

用途：

- 判断哪些 chunk 被保留或过滤。
- 支持人工分析“答案错是检索错、筛选错还是生成错”。

### 6.3 Citation 字段

```text
final_citation_chunk_ids
final_citation_count
citation_mismatches
```

用途：

- 判断引用是否过宽。
- 判断最终 citation 是否直接支撑核心 claim。

### 6.4 Self-check 字段

```text
support_verdict
unsupported_claims
missing_required_items
revision_instruction
```

用途：

- 判断 self-check 是否真正发现问题。
- 判断是否给出具体可执行修正，而不是泛泛要求重答。

## 7. 当前技术边界

C3-lite 不是万能方案。

适合 C3 的任务：

- 多文档比较；
- 模糊或省略查询；
- 需要多对象覆盖的任务；
- 证据不足判断；
- 需要严格引用支撑的复杂知识任务。

不适合强行走 C3 的任务：

- 简单事实问答；
- 单文档关键词明确问题；
- 计算题；
- 表格分析题；
- 代码执行题；
- 工具调用型任务。

这些任务后续应交给 C2 快速路径或 C4 工具路径，而不是继续增加 C3 的复杂度。

## 8. 后续优化方向

后续不建议继续盲目增加检索轮数。更优先的方向是：

1. 优化 required-items 抽取，减少多对象题漏项。
2. 优化 comparison 类答案模板，避免混淆分类体系。
3. 继续收紧 citation selection，提升 chunk-level 引用准确性。
4. 对 Q005、Q006、Q012、Q015、Q023、Q027 做人工复核。
5. C4 开始接管 table_analysis、calculation、code_execution 等工具型任务。
6. 系统级 Demo 可使用 route policy，但论文式实验中必须区分“纯 C3 能力”和“路由系统收益”。

## 9. 阶段性结论

C3-lite 的技术价值不在于“比 C2 对所有题都更好”，而在于：

```text
在复杂知识任务中，通过有限查询预算、多查询融合、证据筛选、
覆盖清单、claim-citation 绑定和 claim-level self-check，
以明显低于旧版 C3 的成本，保持接近旧版 C3 的答案质量。
```

这比“无限多轮检索”的 Agentic RAG 更适合当前课题，因为它更可控、更容易解释，也更符合 50 天左右研究周期内的工程可完成性。

## 10. 参考开源项目与借鉴内容

本项目没有直接复刻某一个开源 Agentic RAG 系统，而是参考多个公开项目和框架的关键思想，再结合本课题的时间、人力和测试集规模做轻量化实现。参考内容分为三类：技术机制参考、横向系统参考和评测思想参考。

### 10.1 技术机制参考

| 项目 / 资料 | 参考内容 | 本项目对应实现 | 未采用内容 |
| --- | --- | --- | --- |
| Self-RAG / `AkariAsai/self-rag` | 按需检索、自我批判、判断生成内容是否被证据支撑 | `claim-level self-check`、`support_verdict`、`unsupported_claims`、证据不足时保守回答 | 未训练专门模型，未复现原论文完整训练与标记体系 |
| CRAG / Corrective RAG 相关实现 | 检索后进行文档相关性评估，对低质量证据进行纠正或过滤 | `Evidence Grader`，将 chunk 标为 `direct / partial / background / irrelevant` | 未接入外部大规模网络搜索纠错，不做重型检索重写循环 |
| LangGraph Self-RAG / CRAG 教程 | `retrieve -> grade documents -> generate -> check` 的图式流程 | C3 的 planning、RAG sub-agent、Evidence Grader、claim-level self-check 分层编排 | 未完整使用 LangGraph 图节点重构整个系统，保留现有工程入口 |
| agentic-rag-for-dummies | 多子查询、上下文压缩、自纠错、模块化 Agentic RAG 思路 | RAG 查询预算、多查询去重、RRF 融合、证据压缩与日志字段 | 未做完整 parent-child indexing，仅保留后续优化方向 |
| Reciprocal Rank Fusion 相关检索融合思想 | 多查询或多检索器结果融合时，用排名倒数加权提高稳定性 | `multi_query_fusion="rrf"`，多子查询结果按 `chunk_id` 去重后融合 | 未引入更复杂的学习排序模型 |

这些参考项目的共同点是：它们不把 RAG 看成“一次检索 + 一次生成”，而是强调检索质量判断、证据筛选、生成后检查和必要时修正。本项目 C3-lite 的设计也沿用了这一思想，但将其压缩为低成本、可解释、适合本科短周期实现的版本。

### 10.2 横向系统参考

| 系统 | 参考定位 | 当前状态 |
| --- | --- | --- |
| Dify | 开源 LLM 应用平台，支持工作流、知识库和 Agent 编排，可作为产品化 ARAG/RAG 系统参考 | 尚未完成同知识库、同题横向实测；后续作为 C5 横向参考 |
| RAGFlow | 开源 RAG 引擎，强调文档解析、知识库问答和 Agentic RAG 能力 | 尚未完成同知识库、同题横向实测；后续作为 C5 横向参考 |
| FastGPT / QAnything | 开源知识库问答系统，可作为 RAG 产品形态和知识库处理参考 | 当前未进入正式对照，必要时作为补充参考 |

需要注意：Dify / RAGFlow 目前不能写成“已经完成对比实验”。当前已完成的是 C0-C3 内部模块对比；Dify / RAGFlow 后续应在 C5 阶段使用同一知识库、同一测试题和尽量一致的模型设置进行横向参考。

### 10.3 评测思想参考

| 框架 / 思想 | 参考内容 | 本项目对应指标 |
| --- | --- | --- |
| RAGAS | answer correctness、faithfulness、context precision/recall 等 RAG 评测思想 | Answer Correctness、Faithfulness、Citation Accuracy、Gold Doc/Chunk Coverage |
| ARES | 使用模型辅助评测 RAG 答案质量和证据支撑 | AI Judge 辅助评分，但最终结论仍需人工复核 |
| RAGChecker | 将 RAG 错误拆成检索错误、生成错误、证据不一致等类别 | main problem、failure type、unsupported claim、citation mismatch |
| RAGTruth | 对 hallucination、unsupported claim、错误拒答等问题分类 | over-refusal、unsupported claim、evidence insufficient 等失败分析 |

本项目没有直接接入这些框架的完整测试集，而是借鉴其指标思想，并结合自建测试集进行量化评测和人工复核。原因是本课题需要评估自己的知识库、自己的 C0-C4 模块和工具调用链路，完全套用公共 Benchmark 无法覆盖所有实验目标。

## 11. 已完成对比结果

当前已完成的量化对比主要是 C2/C3 内部模块对比，不包含 Dify / RAGFlow 横向系统实测。

### 11.1 C2/C3 30 题版本对比

| 配置 | 成功题数 | 平均延迟 | 平均 RAG 次数 | Answer Correctness | Citation Accuracy | Faithfulness | 综合分 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C2 Stage2 old | 30/30 | 21.2s | 1.00 | 0.683 | 0.667 | 0.950 | 0.738 |
| C2 Stage3 old | 30/30 | 20.8s | 1.00 | 0.633 | 0.650 | 0.983 | 0.725 |
| C2 Stage3 next | 30/30 | 26.0s | 1.00 | 0.533 | 0.617 | 0.950 | 0.658 |
| C3 formal old | 30/30 | 156.7s | 10.87 | 0.767 | 0.750 | 0.950 | 0.808 |
| C3 conservative old | 30/30 | 98.3s | 5.37 | 0.733 | 0.767 | 0.917 | 0.792 |
| C3-lite-next | 30/30 | 41.6s | 1.60 | 0.750 | 0.717 | 0.967 | 0.796 |

### 11.2 对比结论

1. C3-lite-next 相比 C3 conservative old，平均延迟从 98.3s 降至 41.6s，平均 RAG 次数从 5.37 降至 1.60，综合分从 0.792 小幅升至 0.796。
2. C3-lite-next 相比 C3 formal old，综合分略低 0.012，但延迟约为旧 formal C3 的 26.6%，RAG 调用次数约为旧 formal C3 的 14.7%。
3. C3-lite-next 相比 C2 Stage2，在复杂任务上更有优势，但在 simple_qa、calculation、code_execution 等任务上成本更高，不应作为所有题的默认路径。
4. C2 Stage3 next 退化明显，低于 C2 Stage2 和 C2 Stage3 old，因此该方案已本地备份并从代码口径回退。
5. 当前最稳的 C2 主基线仍是 C2 Stage2；C2 Stage3 old 只作为上下文扩展边界对照；C3-lite-next 是当前 C3 主方案。

### 11.3 按任务类型观察

当前 C3-lite-next 的优势主要集中在：

- `multi_doc`：需要整合多个文档、多个概念或多个系统。
- `fuzzy_query`：问题表达模糊，需要规划前改写和子查询拆解。
- `insufficient_evidence`：需要判断资料是否足以支持结论。

收益有限的任务：

- `simple_qa`：C2 Stage2 通常已经足够。
- `calculation`：应交给 C4 计算器工具，而不是 C3 文本检索。
- `table_analysis`：应交给 C4 表格分析工具。
- `code_execution`：应交给 C4 代码执行工具。

因此，后续系统 Demo 可以借鉴路由思想：简单检索题走 C2，复杂知识题走 C3，工具型题走 C4。但在论文式实验汇报中，必须区分“纯 C3 能力”和“系统路由收益”。

## 12. 后续横向对比计划

Dify / RAGFlow 横向参考建议放在 C5 阶段，目标不是证明自研系统全面优于成熟开源系统，而是提供一个市场常见方案参照。

建议对比方式：

1. 使用同一批学习资料和技术资料作为知识库。
2. 使用同一组测试题，优先选 10-15 道代表题。
3. 记录同类指标：答案正确性、引用可信度、是否能处理多文档问题、响应延迟。
4. 不参与 C0-C4 模块消融，只作为横向参考。
5. 若 Dify / RAGFlow 配置能力与自研系统不完全一致，应在报告中说明限制。

推荐表述：

```text
本课题已完成 C0-C3 内部模块对比实验。Dify / RAGFlow 将作为 C5 横向参考，
使用同一知识库和同一测试任务进行小规模对比，用于观察自研 C3-lite 与
开源 RAG/Agentic RAG 系统在复杂知识任务中的差异。
```
