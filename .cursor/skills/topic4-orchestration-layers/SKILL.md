---
name: topic4-orchestration-layers
description: >-
  Topic4 多层级编排（main.py agent）的职能划分：第一层解析填槽、第二层工具执行、
  第三层研判调度。在修改 session_planner、agent_runner、judge_layer、orchestration/loop
  或向用户解释「规划层是否执行代码/路径」时应用本 Skill。
---

# Topic4 编排三层职能（明确 Skill 边界）

**编排外壳**（`orchestration/` 调度循环、`agent_cli` 入口与 `OrchestrationConfig`）为课题迭代中**新增/重写**；**复用**既有 `experiment.runner`、`kb_index_builder`、`tools_factory` 中的 RAG 与入库工具封装。

本仓库的 `main.py agent` 使用 **同一套对话模型（DeepSeek 兼容）** 分三次（或多次）调用，**角色不同**，类似「同一人格、不同工牌」：

| 层 | 代码入口 | Skill / 职责 | 明确不做 |
|----|-----------|----------------|----------|
| **L1 规划** | `session_planner.run_layer1_session_plan` | 把用户**整段原文**吃进去，**解析并填入** JSON：路径候选、任务摘要、是否需要 RAG、给第二层的 `plan_for_layer2`、管线建议 | 不执行代码、不跑检索、不写入 Chroma、不调沙箱 |
| **L2 执行** | `agent_runner.build_topic4_deep_agent` + `tools_factory` | 根据 L1 与用户原文，**决定并调用工具**：`topic4_rag_query`、`topic4_kb_ingest`、`sandbox_exec_python` 等 | 不负责输出 L1 那种完整 JSON 规划（但可纠正理解并继续工具闭环） |
| **L3 研判** | `judge_layer.run_orchestration_judge` | 根据目标、L1 摘要、L2 摘录（及可选 KB 对齐）做 **complete / continue / replan / 问用户** | 不重新从长文中抠路径/代码；不调工具 |

## 与用户直觉对齐

- **「模型负责解析」**：在 **L1** 体现为「抽路径 + 填槽」；在 **L2** 体现为「把任务拆成工具参数（ question、file_path、code）」。
- **「路径 / 代码 / 自然语言」**：**解析**主要由 L1+L2 的提示词引导；**执行**只发生在 L2 的工具调用。
- **终端（PowerShell）不是任一层**：在 `PS>` 粘贴的内容若未进入 Python 进程，则**不会**到达 L1。

## 修改提示词时的检查清单

- [ ] L1 的 `LAYER1_SYSTEM_PROMPT` 是否仍强调「仅 JSON、无工具」？
- [ ] L2 的 `DEFAULT_AGENT_SYSTEM_PROMPT` 是否仍强调「一切可执行动作走工具」？
- [ ] L3 的 `LAYER3_SYSTEM_PROMPT` 是否仍强调「只研判、不抠路径」？

## 相关路径

- `src/agentic_rag/deep_planning/session_planner.py` — L1
- `src/agentic_rag/deep_planning/agent_runner.py` — L2 系统提示
- `src/agentic_rag/orchestration/judge_layer.py` — L3
- `src/agentic_rag/orchestration/loop.py` — 调度循环
