# Agent Runtime 架构说明（Topic4）

本文档说明 `src/agentic_rag/runtime/` 与既有 C3/C4 编排的关系、完成度及借鉴点。

## 设计目标（对齐规范 0–11）

| 层级 | 目录 | 职责 |
|------|------|------|
| 入口与启动 | `runtime/entrypoints/cli_router.py`, `main.py` | fast-path（`--version`）、动态导入、模式分流 |
| 环境 | `runtime/setup.py` | 密钥/根目录校验，不做推理 |
| 交互壳 | `runtime/interaction/repl.py` | 输入/展示/斜杠命令，转发引擎 |
| 无头壳 | `runtime/headless/runner.py` | 批量任务、JSON/text 输出 |
| 会话引擎 | `runtime/engine/query_engine.py` | 多轮 `submit_message`、预算、状态落盘 |
| 推理循环 | `runtime/engine/query_loop.py` | 包装 `orchestrate_user_turn`，统一事件 |
| 工具治理 | `runtime/tools/governance.py` | C3/C4 过滤、装配、埋点钩子 |
| 状态 | `runtime/state/*` | `AppState` + `AppStateStore` + `on_change_app_state` |
| 扩展（后置） | `extensions` 槽位 | MCP 连接管理尚未实现 |

## 与 C3/C4 既有实现的关系

**保留并复用（不重复造轮子）：**

- 多层级编排：`orchestration/loop.py` → `orchestrate_user_turn`
- 规划/执行/研判：`session_planner`, `agent_runner`, `judge_layer`
- 工具实现：`deep_planning/tools_factory.py`（`enable_c4_tools` 开关）
- 对外产品入口：`main.py client`（Gradio/控制台）→ 内部经 `c34_client.run_c34_turn` 调用 `QueryEngine`
- 多文档与会话检索范围：`documents/multi_doc.py`、`prepare_document_scope_from_input`（`c34_client.py`）
- 传入检查与去重入库：`documents/ingest_inspector.py`（`resolve_session_doc_ids` 复用已有 doc_id）
- 客户端审计：`telemetry/audit_log.py` → `runs/logs/audit/global_audit.jsonl`（`client_hooks` 接线，不参与模型）

**新增骨架价值：**

- REPL 与 headless 共用 `QueryEngine`，避免第三套推理路径
- 集中 `AppState`，副作用只在 `effects.py`
- 启动 profiling checkpoint（stderr `[profile] ...`）
- 无头 `topic4.headless.v1` 报告 schema

## 启动方式

```powershell
# 既有 Topic4 CLI（经 router 回落）
uv run python main.py client --console --c3
# 多文档（入库 Chroma 后会话内按 doc_id 子集检索）
uv run python main.py client --console --c3 data/raw/tech_docs/a.md data/raw/tech_docs/b.md
uv run python main.py client --docs-text "data/raw/a.md 和 data/raw/b.md"

# 新 Runtime REPL（需 agent 组 + .env）
uv run python main.py runtime repl --c3
uv run python main.py runtime repl --c4 --sandbox

# 无头批处理（tasks 文件每行一题）
uv run python main.py runtime headless --tasks data/testset/questions_headless_sample.txt --format json

# fast-path
uv run python main.py --version
```

## 模式分流

| 条件 | 行为 |
|------|------|
| `--version` / `-V` | 立即打印版本并退出 |
| 首参 `runtime` | `run_runtime_main` → `repl` 或 `headless` |
| 其他 | 原有 `cli/app.py` 子命令 |

## 当前完成度

| 模块 | 状态 | 说明 |
|------|------|------|
| cli_router | ✅ 最小 | version + 动态导入 + profile |
| main / setup | ✅ 最小 | repl/headless 分流；bare 模式未单独暴露 |
| QueryEngine + query_loop | ✅ | 包装编排；未拆成细粒度 tool_use 迭代 |
| tools governance | ✅ | 封装 tools_factory；示例 read/search/calc 未单独实现 |
| AppState + effects | ✅ | 档位/权限/文档绑定提示 |
| REPL | ✅ | 多行 END、/quit /retry /hint |
| headless | ✅ | text/json/stream-json；continue-on-error |
| MCP | ⏳ 未做 | `AppState.extensions` 预留 |
| Gradio client | ✅ | `c34_client`：C3/C4 档位、多路径入库、检查表 Markdown、Gradio 6 messages 格式 |
| 多文档 doc_id 子集检索 | ✅ | `kb_doc_ids` → `run_knowledge_base_rag(allowed_doc_ids=…)` |
| 传入文件检查 / 重复内容跳过入库 | ✅ | `ingest_inspector` + `build_session_document_scope` |
| 全局审计 JSONL | ✅ | `telemetry/`；与实验 `run_logs.jsonl` 分离 |
| 对话内附件 / URL 抓取 | ❌ | 须在「开始会话」路径框登记本地文件；无 `fetch_url` 工具 |
| Gradio「规划前改写」开关 | ⏳ | `enable_planning_query_rewrite` 默认关；`main.py agent --planning-rewrite` 已支持 |
| 细粒度 query 迭代（tool_result 回灌事件） | ⏳ | 仍依赖 Deep Agents 内部循环 |

## 日志双线（勿混用）

| 产品线 | 路径 | 何时写入 |
|--------|------|----------|
| 批量实验 A 线 | `runs/logs/<config>/run_logs.jsonl` | `main.py experiment` / `rag` 等，`RunProfile.save_jsonl_log=True` |
| 客户端 B 线 | `runs/logs/audit/global_audit.jsonl` | `main.py client` / `QueryEngine` 编排钩子等 |

## 下一步建议

1. 在 `orchestration` hooks 中发射 `tool_start`/`tool_end` 事件，补齐可追溯轨迹。
2. 将 `main.py agent` 逐步迁到 `runtime repl`，减少 `run_cli_agent_session` 双路径。
3. 实现 `runtime/mcp/connections.py`（指数退避重连）并写入 `AppState.extensions`。
4. headless 对接 `data/testset/questions.csv` 列映射与 `runs/results` 落盘。

## 测试

- `tests/test_runtime_cli_router.py`
- `tests/test_runtime_state.py`
- `tests/test_runtime_tools.py`
- `tests/test_ingest_inspector.py`（传入检查、`resolve_session_doc_ids`）

运行：`uv run pytest tests/test_runtime_*.py tests/test_ingest_inspector.py -q`

## 修订记录

| 日期 | 摘要 |
|------|------|
| 2026-05-17 | 对齐 `c34_client`、多文档入库、审计线、`ingest_inspector` 去重；补充完成度表与日志双线说明。 |
