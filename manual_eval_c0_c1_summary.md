# C0/C1 人工评测简表

## 1. 说明

这份总结基于最新的：

- `runs/results/c0_results.csv`
- `runs/results/c1_results.csv`
- `data/testset/manual_eval_c0_c1.csv`

其中 `manual_eval_c0_c1.csv` 目前是人工评分草稿，状态还是 `draft_needs_human`，但已经按这轮新结果重做。

## 2. 平均分

| config | answer_correctness | citation_accuracy |
| --- | ---: | ---: |
| c0_naive | 0.525 | 0.65 |
| c1_rewrite | 0.4 | 0.55 |

## 3. 简单结论

- 这轮人工评分里，`C0` 整体比 `C1` 更稳
- `C1` 虽然多命中了一些目标文档，但没有稳定转化成更好的最终答案
- `C1` 在部分题目里还出现了“改写后答偏”的情况

## 4. 主要现象

- `Q005`：`C0` 能答对 `Self-RAG`，`C1` 改写后反而答成了 `CRAG`
- `Q018`：`C0` 和 `C1` 都没把代码题关键信息读出来
- `Q013`：两边都不擅长做论文列表归类统计
- `Q007`、`Q014`、`Q015`：都能答到一点，但整理不完整

## 5. 当前判断

如果只看这轮结果：

- `C1` 不是稳定更强
- `C1` 的主要代价是更慢、token 更多
- 当前更值得优化的是检索后的整理能力、代码题阅读能力、以及减少改写带来的概念漂移
