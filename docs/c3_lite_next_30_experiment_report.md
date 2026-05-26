# C3-lite-next 30 题实验报告

更新日期：2026-05-27

## 1. 实验目的

本次实验用于验证当前 C3 低成本优化版（下称 C3-lite-next）在 30 道主测试题上的整体效果，并与 C2 Stage2、C2 Stage3 以及旧版 C3 结果进行对比。

本轮重点不是证明 C3 在所有任务上都优于 C2，而是回答三个问题：

1. C3-lite-next 是否能在显著降低延迟和 RAG 调用次数的前提下，保持接近旧版 C3 的答案质量。
2. C3 相比 C2 Stage2 / Stage3 的主要收益体现在哪些任务类型上。
3. 当前 C2 Stage3 next 优化是否可以作为正式 Stage3 方案。

## 2. 实验配置

测试集为 30 题：

- Q001-Q020：主测试集。
- Q021-Q030：C3 候选复杂检索题。

C3-lite-next 运行口径：

```text
--planning-rewrite
--no-adaptive-route
--c3-conservative-opt
```

说明：

- 开启 planning rewrite，是为了保证模糊题和复杂题能先进行规划前改写。
- 关闭 adaptive route，是为了避免把“简单题路由到 C2”的收益误写成 C3 自身收益。
- 开启 conservative opt，包含 RAG 查询预算、重复查询抑制、Evidence Grader、claim-citation binding 和 claim-level self-check。

## 3. C3-lite-next 优化内容

本轮 C3 的主要优化点包括：

1. 限制 RAG 调用预算，避免 C3 对简单题过度拆解和反复检索。
2. 引入 multi-query RRF 融合，使多子查询检索结果先去重融合，再进入答案生成。
3. 引入 Evidence Grader，对候选 chunk 进行轻量证据筛选。
4. 优化答案生成提示，要求先做 required-items 覆盖清单，再生成最终答案。
5. 强化 claim 与 citation 的绑定，每条核心结论只保留必要引用。
6. 强化 claim-level self-check，要求指出 unsupported claims、missing required items、citation mismatches 和具体 revision instruction。

## 4. 30 题总体结果

AI Judge 辅助评分结果如下。该结果用于阶段性分析，最终结论仍需结合人工复核。

| 配置 | 成功题数 | 平均延迟 | 平均 RAG 次数 | Answer Correctness | Citation Accuracy | Faithfulness | 综合分 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C2 Stage2 old | 30/30 | 21.2s | 1.00 | 0.683 | 0.667 | 0.950 | 0.738 |
| C2 Stage3 old | 30/30 | 20.8s | 1.00 | 0.633 | 0.650 | 0.983 | 0.725 |
| C2 Stage3 next | 30/30 | 26.0s | 1.00 | 0.533 | 0.617 | 0.950 | 0.658 |
| C3 formal old | 30/30 | 156.7s | 10.87 | 0.767 | 0.750 | 0.950 | 0.808 |
| C3 conservative old | 30/30 | 98.3s | 5.37 | 0.733 | 0.767 | 0.917 | 0.792 |
| C3-lite-next | 30/30 | 41.6s | 1.60 | 0.750 | 0.717 | 0.967 | 0.796 |

## 5. 阶段性结论

### 5.1 C3-lite-next 有效降低成本

相比 C3 conservative old：

- 平均延迟从 98.3s 降至 41.6s。
- 平均 RAG 调用次数从 5.37 降至 1.60。
- 综合分从 0.792 小幅提升至 0.796。

这说明当前 C3 优化方向有效：不是继续增加检索，而是通过预算控制、证据筛选、答案提示和 self-check 提升单位成本下的答案质量。

### 5.2 C3 的收益主要出现在复杂知识任务

按题型看，C3-lite-next 在 multi_doc、fuzzy_query 和 insufficient_evidence 类任务上更有价值：

- multi_doc：平均综合分 0.854，高于 C2 Stage3 next 的 0.594。
- insufficient_evidence：平均综合分 0.938，高于 C2 Stage3 next 的 0.750。
- fuzzy_query：平均综合分 0.675，高于 C2 Stage3 next 的 0.625。

但 simple_qa、calculation、code_execution 题型中，C2 已经基本够用。C3 在这些题上会带来额外延迟，不应作为所有任务的默认路径。

### 5.3 C2 Stage3 next 不适合作为正式增强方案

当前 C2 Stage3 next 的综合分为 0.658，低于：

- C2 Stage2 old：0.738。
- C2 Stage3 old：0.725。

因此 C2 Stage3 next 应作为失败优化尝试记录，不作为正式 Stage3 结论。代码层面已将 C2 Stage3 回退为旧版口径：C2 Stage2 + 邻接 chunk 上下文扩展，不叠加 Evidence Grader。

## 6. 主要失败题与风险

当前 C3-lite-next 仍需人工复核以下题目：

| 题号 | 问题类型 | 当前风险 |
| --- | --- | --- |
| Q005 | 复杂检索 / 多对象 | 答案可能漏关键对象或引用不足 |
| Q006 | 检索型问答 | 答案正确性与引用准确性较旧版下降 |
| Q012 | 多文档比较 | 仍可能混淆两个分类体系 |
| Q015 | 多文档总结 | 答案完整性下降 |
| Q023 | C3 候选复杂题 | 分类维度和方法映射不够稳定 |
| Q027 | 模糊查询 | 对模糊意图的覆盖仍需人工判断 |

这些题不能只看 AI Judge 分数，必须由唐宁进行人工复核，并记录 main problem。

## 7. 后续工作

1. 冻结 C2 主结论：C2 Stage2 作为稳定主基线，C2 Stage3 old 作为边界对照。
2. 保留 C3-lite-next 作为当前 C3 主方案，但在报告中明确其适用边界。
3. 对 Q005、Q006、Q012、Q015、Q023、Q027 做人工复核。
4. C4 不应继续等待 C3 完全完美，可以进入工具型任务 smoke 与正式实验。
5. 后续若做系统级低成本方案，可把 simple_qa 等题型路由到 C2，但不能把该收益写成纯 C3 收益。

