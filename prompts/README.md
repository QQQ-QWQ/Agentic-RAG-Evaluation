# prompts 目录

本目录用于存放 Prompt 模板。

Prompt 不要全部写死在代码里，因为 Prompt 会影响实验结果。正式实验前需要冻结 Prompt，并在实验记录中说明使用版本。

已纳入：

```text
query_rewrite_prompt.md
self_check_prompt.md
answer_judge_prompt.md   # run_score_answer_accuracy.py / run_c2_ablation_answer_accuracy.py
rag_multidim_judge_prompt.md   # run_score_rag_multidim.py
```

后续可补充：

```text
task_planner_prompt.md
answer_generation_prompt.md
tool_selection_prompt.md
```
