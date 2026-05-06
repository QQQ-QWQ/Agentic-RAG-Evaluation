# 冻结版本存档目录

用于存放 **C0–C4 各配置正式冻结** 时的可追溯材料，与当前开发中的 `configs/`、`data/`、`prompts/` 区分开。

## 子目录约定

| 子目录 | 对应配置线 |
|--------|------------|
| `c0/` | Naive RAG 基线 |
| `c1/` | Query Rewrite RAG |
| `c2/` | Advanced RAG（BM25 / hybrid / rerank 等） |
| `c3/` | Agentic Retrieval（规划、多轮检索、self-check） |
| `c4/` | Tool-Augmented Agentic RAG |

## 已有快照（示例）

| 子目录 | 快照文件夹 | 说明 |
|--------|------------|------|
| `c0/` | `snapshot_2026-05-06/` | 含 `c0_naive.yaml`、测试集、`documents.csv`、`chunks.jsonl`、`FREEZE.md`。 |
| `c1/` | `snapshot_2026-05-06/` | 含 `c1_rewrite.yaml`、`query_rewrite_prompt.md`、同上数据副本、`FREEZE.md`。 |
| `c2/` | `snapshot_c2_pipeline_v1/` | C2 三阶段检索脚本说明、向量缓存行为、`FREEZE.md`（代码仍以仓库根为准）。 |

后续冻结请新建 **`snapshot_YYYY-MM-DD`** 或 **`tag名称`** 子文件夹，避免覆盖历史快照。

## 建议放入的内容（每次冻结新建一层日期或 tag 名）

在同一配置子目录下，可用例如 `20260506_c1-v1/` 或 `git-tag-c1-v1.0/` 命名文件夹，内含：

- `configs/`：`configs/c*.yaml` 等文件的副本（或当时提交的哈希说明）。
- `prompts/`：参与实验的 prompt 副本。
- `manifest.json` 或 `FREEZE.md`：Git **commit** / **tag**、模型名（不写 API Key）、输入数据版本说明。
- `runs/`：如需归档结果，可复制当时 `runs/results/*.csv`、摘要日志（注意体积；大文件可仅存网盘路径于 manifest）。

正式冻结流程仍以 **`docs/directory_rules.md`** 第九章为准。
