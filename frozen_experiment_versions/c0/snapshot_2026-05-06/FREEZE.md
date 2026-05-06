# C0 Naive RAG — 冻结快照 `snapshot_2026-05-06`

本目录为仓库内 **C0** 对照实验所用材料的自包含副本，便于与主线开发中的 `configs/`、`data/` 区分。

## 对应配置语义

- **配置**：`config/c0_naive.yaml`
- **含义**：普通 RAG 基线；仅文档解析、切块、向量检索 Top-K、生成；**无** query rewrite、BM25、hybrid、rerank、self-check、工具。

## 本快照包含

| 路径 | 说明 |
|------|------|
| `config/c0_naive.yaml` | C0 正式 YAML（与仓库 `configs/` 内同名文件一致）。 |
| `data/testset/questions.csv` | 测试题。 |
| `data/testset/references.csv` | 参考文档与标注占位。 |
| `data/processed/documents.csv` | 知识库文档登记表。 |
| `data/processed/chunks.jsonl` | 切块导出（与批量脚本重建逻辑一致时的快照）。 |
| `prompts/README.md` | Prompt 目录说明。 |

## 未单独文件化部分

C0 **答案生成**侧系统提示词若以代码内默认字符串为准，请以冻结时的 **`src/agentic_rag/pipelines/local_rag.py`**（及关联模块）为准；正式报告请写明 **Git commit / tag**。

## 复现实验时还需对齐

1. **代码**：与冻结提交一致的 `src/agentic_rag/`（尤其是 `run_batch_experiments.py`、`local_rag.py`）。
2. **模型**：`.env` 中 `ARK_EMBEDDING_MODEL`、`ARK_EMBEDDING_DIMENSIONS`、`DEEPSEEK_CHAT_MODEL` 与实验记录一致（勿提交密钥）。
3. **原始正文**：`documents.csv` 中 `file_path` 指向的 `data/raw/...` 文件需在仓库中存在且一致。

## Git 版本（请在本机有 `.git` 的克隆里填写）

```text
git_rev: （在此填写 git rev-parse HEAD）
tag:     （可选）
```

生成日期：**2026-05-06**（快照打包日；与仓库内容同步时间点见上 `git_rev`）。
