# C3 Formal 30 题人工复核结论

更新时间：2026-05-24

## 1. 复核对象

本次复核对象为 C3 formal 30 题正式批量结果。

主结果文件：

```text
runs/results/c3_ids_results.csv
```

AI Judge 辅助文件：

```text
runs/results/c3_formal_30_llm_judged.csv
```

人工评分表：

```text
data/testset/manual_eval_c3_formal.csv
```

当前说明：本轮评分为 `ai_assisted_reviewed`，可用于阶段分析和报告草稿，但若要作为最终正式结论，仍建议成员 B 再做人工抽查确认。

## 2. 完整性检查

| 检查项 | 结果 |
| --- | --- |
| 题目范围 | Q001-Q030 |
| 结果表行数 | 30 |
| AI Judge 表行数 | 30 |
| 人工评分表行数 | 30 |
| 程序级 error | 0 |
| `run_logs.jsonl` 解析 | 30 行全部可解析 |

当前结果表和评分表结构可用。

## 3. 人工评分汇总

| 指标 | 平均分 |
| --- | ---: |
| Answer Correctness | 0.800 |
| Citation Accuracy | 0.733 |
| Planning Quality | 0.683 |
| Multi-round Quality | 0.750 |
| Retrieval Sufficiency | 0.883 |
| Self-check Quality | 0.567 |

主要问题分布：

| main_problem | 数量 |
| --- | ---: |
| none | 13 |
| weak_citation | 6 |
| partial_answer | 5 |
| planning_failure | 2 |
| latency_too_high | 1 |
| retrieval_failure | 1 |
| multi_round_noise | 1 |
| unsupported_refusal | 1 |

## 4. 关键观察

### 4.1 C3 在复杂多文档题上确实有价值

表现较好的代表题：

- Q021
- Q022
- Q024
- Q025
- Q026
- Q028
- Q030

这些题的共同点是：

- 需要比较多个框架或方法；
- 需要组合多个证据源；
- 需要把复杂问题拆成结构化答案；
- C3 的 planning / multi-round 行为对最终答案确实有帮助。

### 4.2 C3 在简单题上经常显得过重

代表题：

- Q001
- Q002
- Q003
- Q004
- Q016
- Q018
- Q019

这些题即使答对，也往往不需要完整的 C3 行为链。特别是：

- Q003 为 simple_qa，却出现 12 次 RAG 调用；
- 简单问答和计算题的 planning 收益有限；
- 这类题更适合直接走 C2 或更轻路径。

### 4.3 表格分析和模糊需求拆解仍然不稳定

代表题：

- Q007
- Q008
- Q013
- Q014
- Q015
- Q017
- Q023
- Q027

典型问题包括：

- 多轮检索后仍然偏题；
- 会把“证据不足说明”写得过长，代替真正比较；
- 规划存在，但没有转化为更好的答案结构；
- 四项目分类题也会出现覆盖不全；
- 表格/归类题容易进入“检索很多但没有完成任务”的状态。

### 4.4 引用质量仍是 C3 当前的主要短板

Citation Accuracy 平均分只有 `0.733`，低于本轮 C3 的 Answer Correctness，也低于已冻结的 C2 Stage2 引用表现。

问题主要不是“完全乱引”，而是：

- 引用过宽；
- 夹带与核心结论无关的 chunk；
- 用了一堆相关引用，但最关键的 gold chunk 不够聚焦。

## 5. 阶段结论

当前可以得出的稳妥判断是：

1. C3 formal 已经具备稳定批量运行能力。
2. C3 的确更适合复杂多文档整合、框架比较、角色分工、复杂任务边界判断这类题。
3. C3 还不适合作为所有题型的默认路径。
4. C3 不能仅凭本轮结果直接写成“显著优于 C2”。

原因有两点：

- 本轮只跑了 C3，没有对同一批 Q001-Q030 做 C2 同题对照；
- C3 虽然 retrieval sufficiency 高，但 planning/self-check/citation 质量并没有同步拉满。

因此，当前更合适的报告口径是：

```text
C3 在复杂多文档和任务拆解类问题上显示出价值，
但成本高、路径重、引用质量仍需优化，
暂时不应写成全面优于 C2 的最终结论。
```

## 6. 建议

1. 后续若要证明 C3 相比 C2 的收益，应对 Q021-Q030 或完整 Q001-Q030 做同题 C2 对照。
2. 简单问答、计算、代码定位题应优先走轻路径，不必强制完整 C3。
3. 表格分析与归类题应尽快转交 C4 工具路径验证。
4. C3 下一轮优化重点应放在：
   - citation selection
   - planning prompt 约束
   - multi-round 去重
   - 证据不足时的简洁保守回答
