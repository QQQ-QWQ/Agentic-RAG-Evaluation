# Member B 评测流程

## 1. 当前状态

这次已经按最新代码和最新配置重跑完 `C0` / `C1`。

当前仓库里关键文件有：

- `data/testset/questions.csv`
- `data/testset/references.csv`
- `data/testset/manual_eval_c0_c1.csv`
- `runs/results/c0_results.csv`
- `runs/results/c1_results.csv`
- `docs/manual_eval_c0_c1_summary.md`
- `docs/failure_cases.md`

这轮运行使用的是：

- `DeepSeek` 做生成和改写
- `local embedding fallback`

也就是说，这次结果不是旧结果，文档和人工评分表都已经按这轮新结果同步过了。

## 2. 本轮自动实验结果

### C0

- 题目数：20
- 预期文档命中：18/20
- 平均延迟：5204.7 ms
- 平均总 token：1017.25
- 报错数：0

### C1

- 题目数：20
- 预期文档命中：19/20
- 平均延迟：18431.3 ms
- 平均总 token：1910.65
- 报错数：0

## 3. 本轮人工评分草稿结果

`manual_eval_c0_c1.csv` 已经按这轮结果重做。

### C0

- answer_correctness 平均分：0.525
- citation_accuracy 平均分：0.65

### C1

- answer_correctness 平均分：0.4
- citation_accuracy 平均分：0.55

## 4. 怎么打分

看两个维度：

1. 回答是否正确
2. 引用是否真的支撑答案

分数规则：

- `1`：正确
- `0.5`：部分正确
- `0`：错误、答偏、或基本没完成

## 4.1 LLM-as-judge 辅助评分

项目保留原本设计的 AI Judge 自动化评分机制。它可以用于批量初筛、阶段对比和定位可疑样例，但不能替代人工评分。

当前分两种用法：

1. 旧版答案正确率评分：只输出 `correctness_score`，适合延续 C2 已有实验记录。
2. 新版多维评分：输出 `answer_correctness_score`、`answer_completeness_score`、`citation_accuracy_score`、`faithfulness_score` 和 `llm_judge_weighted_score`。

推荐流程：

1. 先跑自动实验，得到 `runs/results/*.csv`。
2. 再跑 AI Judge，得到 `*_scored.csv` 或 `*_llm_judged.csv`。
3. B 成员优先人工复核低分题、AI Judge 与直觉冲突题、以及会影响结论的关键题。
4. 正式结论以人工评分为准，AI Judge 作为辅助证据写入实验过程。

注意：`codex_precheck` 只是组长临时辅助判断，不作为正式评分文件保留。

## 5. 常用失败标签

- `retrieval_miss`
- `wrong_method`
- `partial_answer`
- `unsupported_refusal`
- `capability_boundary`
- `none`

## 6. 现在的结论

- `C1` 的检索命中率略好
- 但 `C1` 更慢，token 成本更高
- 按这轮人工评分草稿看，`C1` 没有稳定优于 `C0`

所以这轮更适合得出的结论是：

- 查询改写有帮助，但收益不稳定
- 当前主要短板仍然是答偏、代码题检索失败、以及多文档整理能力不足
