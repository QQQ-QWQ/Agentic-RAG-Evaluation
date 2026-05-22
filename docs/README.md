# docs 目录说明

本目录保存项目长期有效的工程规范、架构说明、实验指南、评测规则和实验记录。根目录 `README.md` 只保留开题报告正文与参考文献；当前进度、运行入口和下一步任务统一维护在根目录 `current progress.md`。

## 1. 文档职责边界

| 文件 | 职责 |
| --- | --- |
| `../README.md` | 开题报告正文与参考文献，不再维护运行命令和进度表 |
| `../current progress.md` | 当前进度、运行入口、C0-C4 状态、下一步任务 |
| `docs/README.md` | docs 文档索引和维护规则 |
| `docs/experiment_notes.md` | 按时间记录实验过程、命令、输出、问题和阶段判断 |
| `docs/ARCHITECTURE.md` | 当前工程总架构、模块职责、C3/C4 Runtime 与工具链路 |

不要把同一类内容重复写在多个地方。运行命令优先更新 `current progress.md`；架构变更优先更新 `ARCHITECTURE.md`；实验过程优先更新 `experiment_notes.md`。

## 2. 当前主文档

### 协作与规范

| 文档 | 状态 | 说明 |
| --- | --- | --- |
| `environment_and_git_rules.md` | 维护中 | Python、uv、`.env`、Git 分支、commit、PR 规范 |
| `collaboration_workflow.md` | 维护中 | 三人分工、协作节奏、验收方式；已合并原 `team_roles.md` |
| `directory_rules.md` | 维护中 | 仓库目录、数据目录、runs 输出、冻结规范 |
| `experiment_stage_and_code_ownership.md` | 维护中 | C0-C4 配置、源码归属和阶段边界 |

### 架构与工程说明

| 文档 | 状态 | 说明 |
| --- | --- | --- |
| `ARCHITECTURE.md` | 主文档 | 当前代码结构、C3/C4 Runtime、工具链路、日志审计 |
| `agent_runtime_architecture.md` | 专题文档 | Agent Runtime、`QueryEngine`、headless / client 关系 |
| `c0_baseline_architecture.md` | 历史/基线文档 | C0 单文档 RAG baseline 迁移与结构说明 |
| `interface_and_logging_rules.md` | 维护中 | C0-C2 输入输出结构、日志字段、运行结果格式 |

### 实验运行指南

| 文档 | 状态 | 说明 |
| --- | --- | --- |
| `batch_experiment_guide.md` | 稳定 | C0/C1 批量实验运行和结果解释 |
| `c2_ablation_guide.md` | 维护中 | C2 三阶段消融、Stage3 日志字段和运行说明 |
| `c3_smoke_experiment_guide.md` | 维护中 | C3 Q021-Q030 smoke test、输出文件和人评要求 |

### 评测与结论材料

| 文档 | 状态 | 说明 |
| --- | --- | --- |
| `evaluation_plan.md` | 维护中 | 人工评分指标、判定规则、C3/C4 待补字段 |
| `evaluation_ai_judge.md` | 维护中 | AI Judge / LLM-as-judge 的定位、多维评分字段和限制 |
| `manual_eval_c0_c1_summary.md` | 阶段总结 | C0/C1 人工评分摘要 |
| `c2_three_layer_retrieval_report.md` | 阶段总结 | C2 三阶段检索实验专题报告 |
| `failure_cases.md` | 待扩充 | 失败案例库，后续至少整理 10 个典型案例 |

## 3. 已合并或不再单独维护的内容

| 内容 | 当前处理 |
| --- | --- |
| `team_roles.md` | 已合并到 `collaboration_workflow.md`，不再单独维护 |
| 根目录 README 的运行入口和进度表 | 已移入 `current progress.md` |
| C4 工具和 C3/C4 批量进度 | 以 `current progress.md` 和 `ARCHITECTURE.md` 为准 |
| 每次实验临时输出 | 不写入 docs 索引，记录在 `experiment_notes.md`，原始文件留在本地 `runs/` |

当前没有直接删除 docs 文件。若后续需要真正删除历史文档，应先由组长确认，再统一提交。

## 4. 建议后续补充的文档

这些文档只有在对应阶段真正开始时再建，不需要提前空转：

| 文档 | 建议时机 | 作用 |
| --- | --- | --- |
| `data_description.md` | 测试集扩至 40-50 题时 | 记录知识库来源、doc_id、chunk_id、数据冻结版本 |
| `demo_script.md` | Demo 前一周 | 记录现场演示脚本、备用问题和异常处理方案 |
| `final_report_outline.md` | 结题报告前 | 整理最终报告结构、图表和结论 |
| `slides_outline.md` | PPT 前 | 整理答辩页结构、成员讲解分工 |

## 5. 文档维护规则

1. 与实验结论有关的内容必须能追溯到 `runs/` 输出、人工评分表或 `experiment_notes.md`。
2. 与接口、日志、数据字段有关的修改，要同步更新对应实验指南。
3. `current progress.md` 用于当前进度，不写成永久规范。
4. `experiment_notes.md` 是过程记录，不替代最终报告。
5. 不把 `.env`、API Key、个人路径、临时大文件或本地 `archive/` 内容写进文档。

## 6. 组长检查清单

赵启行每次阶段推进前建议检查：

- 当前 main 是否与远端同步。
- 三个人是否都能 `uv sync` / `uv sync --group agent`。
- C3/C4 是否有 batch 日志、人工评分和失败案例。
- 是否有成员把 `runs/`、`.env`、`archive/` 或无关大文件提交到仓库。
- 新增功能是否更新了 `ARCHITECTURE.md` 或对应实验指南。
- 当前结论是否区分“工程能跑”“自动指标较好”“人工评分可信”。
