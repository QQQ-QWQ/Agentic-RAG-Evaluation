---
name: topic4-orchestration-layers
description: >-
  Topic4 多层级编排（main.py agent）的职能划分：第一层解析填槽、第二层工具执行、
  第三层研判调度；以及第二层内置工具清单与扩展钩子。在修改 session_planner、
  agent_runner、judge_layer、orchestration/loop、tools_factory 或向用户解释
  「规划层是否执行代码/路径」时应用本 Skill。
---

# Topic4 编排三层职能（明确 Skill 边界）

**编排外壳**（`orchestration/` 调度循环、`agent_cli` 入口与 `OrchestrationConfig`）为课题迭代中**新增/重写**；**复用**既有 `experiment.runner`、`kb_index_builder`、`tools_factory` 中的 RAG 与入库工具封装。

本仓库的 `main.py agent` 使用 **同一套对话模型（DeepSeek 兼容）** 分三次（或多次）调用，**角色不同**，类似「同一人格、不同工牌」：

| 层 | 代码入口 | Skill / 职责 | 明确不做 |
|----|-----------|----------------|----------|
| **L1 规划** | `session_planner.run_layer1_session_plan` | 把用户**整段原文**吃进去，**解析并填入** JSON：路径候选、任务摘要、是否需要 RAG、`kb_mutation_intent`、给第二层的 `plan_for_layer2`、管线建议；**知晓**第二层有哪些工具以便在 `plan_for_layer2` 中排任务顺序 | 不执行代码、不跑检索、不写入 Chroma、**不调任何 LangChain 工具** |
| **L2 执行** | `agent_runner.build_topic4_deep_agent` + `tools_factory` | 根据 L1 与用户原文，**决定并调用工具**（见下表） | 不负责输出 L1 那种完整 JSON 规划（但可纠正理解并继续工具闭环） |
| **L3 研判** | `judge_layer.run_orchestration_judge` | 根据目标、L1 摘要、L2 摘录（及可选 KB 对齐）做 **complete / continue / replan / 问用户** | 不重新从长文中抠路径/代码；不调工具 |

## 第二层内置工具（仅 L2 调用；L1 只在 `plan_for_layer2` 中编排顺序）

| 工具 | 用途 | 安全/范围要点 |
|------|------|----------------|
| `topic4_list_rag_pipelines` | 列出 RAG 管线 id | 只读说明 |
| `topic4_rag_query` | 全库或绑定单文档 RAG | 走既有 Chroma / runner |
| `topic4_kb_ingest` | 登记 `documents.csv` 并重建索引 | 路径须在 **工程根**内 |
| `topic4_file_to_markdown` | [MarkItDown](https://github.com/microsoft/markitdown) 将 PDF/Office/HTML 等转 Markdown | 路径须在 **工程根**内；`MARKITDOWN_MAX_FILE_BYTES` 限体积；`enable_plugins=False` |
| `sandbox_exec_python`（可选） | 在**会话临时目录**内 `python` 执行片段 | 需 `SANDBOX_ENABLED=true` + 编排未 `--no-sandbox`；**非** VM 级隔离 |

**扩展（任意时机追加工具）**：在创建第二层 Agent 时（每轮 `agent is None` 重建时），`OrchestrationHooks.extend_agent_tools` 可返回额外 LangChain 工具，与上表合并。适合接入团队自研工具、远端 E2B/Cube 封装等（需自行实现 Tool 与鉴权）。

## Skill 是否「有必要」？

- **不强制**：模型仅读代码与 `session_planner` / `agent_runner` 系统提示也能工作。  
- **有价值**：多人协作、改提示词时，用本 Skill 统一 **L1/L2/L3 边界** 与 **工具清单**，减少「规划层误以为自己能调工具」等回归。  
- **与提示词关系**：Skill 给 **人类与 Cursor** 看；**模型**主要看 `LAYER1_SYSTEM_PROMPT`、`DEFAULT_AGENT_SYSTEM_PROMPT`（仓库已同步工具名）。二者互补，不必二选一。

## 与用户直觉对齐

- **「模型负责解析」**：在 **L1** 体现为「抽路径 + 填槽 + 入库意图」；在 **L2** 体现为「把任务拆成工具参数（ question、file_path、code）」。
- **「路径 / 代码 / 自然语言」**：**解析**主要由 L1+L2 的提示词引导；**执行**只发生在 L2 的工具调用。
- **终端（PowerShell）不是任一层**：在 `PS>` 粘贴的内容若未进入 Python 进程，则**不会**到达 L1。

## 修改提示词时的检查清单

- [ ] L1 的 `LAYER1_SYSTEM_PROMPT` 是否仍强调「仅 JSON、无工具」，且列出 L2 工具供 `plan_for_layer2` 编排？
- [ ] L2 的 `DEFAULT_AGENT_SYSTEM_PROMPT` 是否仍强调「一切可执行动作走工具」，且包含 `topic4_file_to_markdown`？
- [ ] L3 的 `LAYER3_SYSTEM_PROMPT` 是否仍强调「只研判、不抠路径」？

## 相关路径

- `src/agentic_rag/deep_planning/session_planner.py` — L1
- `src/agentic_rag/deep_planning/agent_runner.py` — L2 系统提示、`build_topic4_deep_agent`（`additional_tools`）
- `src/agentic_rag/deep_planning/tools_factory.py` — LangChain 工具注册
- `src/agentic_rag/tools/markitdown_tool.py` — MarkItDown 封装
- `src/agentic_rag/orchestration/registry.py` — `OrchestrationHooks`（`extend_agent_tools`、`planning_context_enricher`）
- `src/agentic_rag/orchestration/judge_layer.py` — L3
- `src/agentic_rag/orchestration/loop.py` — 调度循环
