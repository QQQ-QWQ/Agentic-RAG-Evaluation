# C1 Query Rewrite RAG — 冻结快照 `snapshot_2026-05-06`

本目录为仓库内 **C1** 对照实验所用材料的自包含副本（在 **C0** 基础上仅增加 query rewrite，与 `batch_experiment_guide.md` 边界一致）。

## 对应配置语义

- **配置**：`config/c1_rewrite.yaml`
- **Prompt**：`prompts/query_rewrite_prompt.md`（与配置中 `prompt_file`、`version: prompt-v2` 对应）
- **含义**：检索式改写、多候选 query、保守改写；**仍关闭** BM25、hybrid、rerank、self-check、工具。

## 本快照包含

| 路径 | 说明 |
|------|------|
| `config/c1_rewrite.yaml` | C1 正式 YAML（`base_config: c0_naive`）。 |
| `prompts/query_rewrite_prompt.md` | Query Rewrite Prompt v2（C1 专用）。 |
| `prompts/README.md` | Prompt 目录说明。 |
| `data/testset/questions.csv` | 测试题（与 C0 同批）。 |
| `data/testset/references.csv` | 参考文档与标注占位。 |
| `data/processed/documents.csv` | 知识库文档登记表。 |
| `data/processed/chunks.jsonl` | 切块导出。 |

## 代码依赖提示

C1 运行时还会读取仓库中的 **`rewrite.py`**、**`schemas.py`** 及 `pipelines` 内 `run_c1_with_index` 等逻辑；冻结应以 **同一 Git commit** 为准。

## 复现实验时还需对齐

1. **模型**：与 C0 相同的 embedding / chat 模型环境变量（实验记录中写明）。  
2. **阈值**：`min_rewrite_confidence` 等见 `c1_rewrite.yaml` 本快照。  

## Git 版本（请在本机有 `.git` 的克隆里填写）

```text
git_rev: （在此填写 git rev-parse HEAD）
tag:     （可选）
```

生成日期：**2026-05-06**。
