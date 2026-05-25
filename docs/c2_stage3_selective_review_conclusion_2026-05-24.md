# C2 Stage3 Selective 人工复核结论

更新时间：2026-05-24

## 1. 复核对象

本次复核对象是新版 C2 Stage3 selective context expansion。

主结果来源：

```text
runs\results\c2_stage3_results_package_2026-05-23\c2_stage3_before_keyword_filter_llm_judged.csv
```

人工评分输出：

```text
data\testset\manual_eval_c2_stage3_selective.csv
```

辅助参考：

```text
runs\results\c2_stage3_results_package_2026-05-23\run_logs.jsonl
runs\results\c2_stage3_results_package_2026-05-23\c2_stage3_keyword_filter_ai_judge_summary.json
runs\results\c2_stage3_results_package_2026-05-23\c2_stage3_no_keyword_filter_ai_judge_summary.json
```

说明：LLM-as-judge 结果只作为辅助定位，不直接作为人工评分。

## 2. 原始运行质量

Stage3 selective 主依据文件与 `current progress.md` 中的自动指标一致：

| 指标 | 数值 |
| --- | ---: |
| 题数 | 20 |
| Error | 0 |
| 文档命中 | 19/20 |
| Gold chunk 命中 | 15/20 |
| 触发 context expansion | 9/20 |
| 平均延迟 | 37056.8 ms |
| 平均 token | 13352.0 |

运行层面可用，没有发现结果表行数缺失或 JSONL 解析失败。

## 3. 人工评分结果

| 配置 | Answer Correctness | Citation Accuracy |
| --- | ---: | ---: |
| C2 Stage2 rerank | 0.800 | 0.800 |
| 旧版 C2 Stage3 fixed context | 0.150 | 0.200 |
| 新版 C2 Stage3 selective context | 0.800 | 0.725 |

新版 Stage3 selective 相比旧版固定扩展有明显恢复：

- 大面积拒答问题明显减少。
- 多数 simple / multi-doc / calculation / code-reading 题可以正常回答。
- 正确率已经恢复到 Stage2 水平。

但它仍没有稳定超过 Stage2：

- 引用准确性低于 Stage2。
- 平均延迟高于 Stage2。
- 平均 token 高于 Stage2。
- 仍有 Q012、Q013 两题出现无支撑拒答。

## 4. 主要问题分布

| main_problem | 数量 |
| --- | ---: |
| none | 10 |
| weak_citation | 4 |
| partial_answer | 4 |
| unsupported_refusal | 2 |

主要问题不是旧版 Stage3 那种系统性拒答，而是：

1. 引用 chunk 过宽或不够贴合 reference。
2. 部分复杂题回答不完整。
3. 少数题仍然错误拒答。

## 5. 重点题观察

### Q005

新版 Stage3 selective 正确识别 Self-RAG，并说明 reflection tokens 和 adaptive retrieval。该题从旧版 Stage3 的错误方法漂移恢复为正确回答。

评分：`1 / 1`

### Q007

答案推荐了 LangChain、RAGFlow、LlamaIndex、LangGraph，但 reference 期望 Dify、RAGFlow、CrewAI、LangGraph。虽然有部分相关项目，但缺少 Dify 和 CrewAI。

评分：`0.5 / 0.5`

### Q012

答案只识别出 2501.09136 的分类方式，并拒绝比较 SoK。该题在 reference 中是可回答的，因此判为无支撑拒答。

评分：`0 / 0.5`

### Q013

答案拒绝对论文类型做分布统计，没有完成表格/列表归类任务。

评分：`0 / 0`

### Q018

答案正确定位 `save_md`，并列出 `subdir`、`filename`、`content`、`source_url` 以及标题、来源 URL、抓取时间等元信息。

评分：`1 / 1`

### Q020

答案正确指出不能证明 Agentic RAG 在所有知识服务任务上都优于普通 RAG，但引用主要支持 Agentic RAG 的优势，未充分支撑全部边界判断。

评分：`1 / 0.5`

## 6. 结论

新版 Stage3 selective 是一次有效优化，已经显著修复旧版固定 context expansion 的退化问题。

但从人工评分看，它仍不应替代 Stage2 作为 C2 冻结版本：

- Stage2：`0.800 / 0.800`
- Stage3 selective：`0.800 / 0.725`

因此，当前 C2 主结论仍建议冻结在：

```text
c2_stage2_c1_hybrid_rerank
```

Stage3 selective 更适合写入报告中的“优化尝试”或“context expansion 风险控制改进”，而不是写成 C2 最优配置。

## 7. 后续建议

1. 在报告中区分旧版 Stage3 fixed context 与新版 Stage3 selective context。
2. 不把 Stage3 selective 的自动指标直接等同于人工质量提升。
3. 后续如果继续优化 Stage3，应优先解决 citation accuracy，而不是继续扩大上下文。
4. C3 smoke 仍需等待原始结果表和逐题日志到位后再评分。
