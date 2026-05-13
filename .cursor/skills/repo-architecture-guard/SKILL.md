---
name: repo-architecture-guard
description: >-
  Audits Agentic-RAG-Evaluation repository structure for redundancy, clarity,
  decoupling, and wiring consistency; prunes clearly obsolete files when safe.
  Apply when opening this project, before refactoring or adding features,
  cleaning the repo, or when the user mentions architecture, redundancy,
  coupling, dead code, or duplicate entrypoints.
---

# 仓库架构守卫（Repo Architecture Guard）

在本仓库（Topic4 / Agentic-RAG-Evaluation）开展**实质性工作**（改代码、加功能、删文件、跑重构）之前：**必须先完整阅读本 SKILL**，并按下列流程执行自检。

---

## 1. 会话开始时（强制）

- [ ] 已读过本 `SKILL.md` 当前全文。
- [ ] 若任务涉及「清理 / 删文件 / 合并脚本」，同时核对下文「允许删除」与「禁止删除」清单。

---

## 2. 架构审视维度（自动检查）

每项用简短结论回答：**通过 / 有风险 / 待改进**，必要时引用路径。

| 维度 | 自问要点 |
|------|-----------|
| **冗余** | 是否存在重复入口（多个 `main` / 多个只做一件事的根脚本）？能否收口到 `main.py` + `src/agentic_rag/cli/`？是否有重复逻辑可复制提取到 `pipelines` / `rag`？ |
| **清晰** | 目录职责是否与 `docs/directory_rules.md`、`docs/ARCHITECTURE.md` 一致？新文件是否放在约定位置（业务在 `src/`，入口在根或 `cli`）？ |
| **解耦** | `documents` / `ark` / `rag` / `llm` 是否避免依赖 `pipelines`？配置是否不经硬编码路径？ |
| **可联通** | 从统一 CLI（`main.py`）或文档中的命令能否对应到真实模块？`import` 链是否在仓库根执行 `uv run python …` 时可解析？新增子命令是否在 `cli/app.py` 注册？ |

---

## 3. 冗余文件处理原则

**在删除任何文件之前：**

1. 用搜索确认 **无引用**：全仓库 `grep` 文件名 / 模块名；检查 `README`、`docs`、测试、`pyproject`。
2. 区分 **废弃脚本** vs **实验产物**：`runs/`、`*.pkl`、日志等多为生成物，优先 `.gitignore` + 本地清理，而非删业务代码。
3. **允许删除**（满足「零引用」或明确废弃）：重复的 demo 壳脚本、已被合并到 `cli/demos.py` 的旧入口、明确标注 temporary 且已过期的草稿。
4. **禁止自动删除**（须用户明确说好才可删）：`tests/`、`data/` 中非占位内容、`configs/`、`prompts/`、`frozen_experiment_versions/`、他人正在用的 `run_*.py`（除非已迁移并更新文档）。

满足「允许删除」且已确认零引用时：**执行删除**，并在同一次变更中更新仍提及该路径的文档（若有）。

---

## 4. 与本项目既有约定对齐

- 批量实验技术栈与入口：`.cursor/rules/topic4-experiment-stack.mdc`。
- 新能力：**函数放进 `src/agentic_rag/`**，CLI 挂 `cli/app.py`，避免再堆根目录 demo。
- 向量持久化：Chroma（`CHROMA_PERSIST_DIRECTORY`）；检索运行时仍为内存 `SimpleVectorIndex`。

---

## 5. 结束时（可选）

若本次改动触及目录结构或入口，用一两句话记录：删了谁、为何安全、入口是否仍唯一。
