# C2 检索消融实验说明

脚本：`run_c2_retrieval_ablation.py`

## 向量索引缓存（避免长时间卡住）

首次运行会对知识库全文切块并调用方舟 **embedding**，耗时取决于 chunk 数量与网络；成功后写入 **`data/processed/.kb_embedding_cache.pkl`**（已 `.gitignore`）。  
源文档与 `documents.csv` 未变化时，再次运行会 **跳过 embedding**，索引构建很快。

- 强制重新 embedding：`--force-rebuild-index`
- 禁用缓存读取：`--no-index-cache`

在同知识库、同测试集（默认 `data/testset/questions.csv` 前 20 条）上顺序跑三组配置：

| 阶段 | 混合检索 | 重排 | 邻接上下文扩展 |
| --- | --- | --- | --- |
| 1 `c2_stage1_c1_hybrid` | 开 | 关 | 关 |
| 2 `c2_stage2_c1_hybrid_rerank` | 开 | 开 | 关 |
| 3 `c2_stage3_c1_hybrid_rerank_context` | 开 | 开 | 开（``--neighbors``） |

默认在 **C1 query rewrite** 之上叠加（与 `configs/c2_advanced.yaml` 基于 C1 的定位一致）；若只想测检索模块可加 `--no-rewrite` 走 C0 链。

### 按阶段单独跑（推荐）

```powershell
uv run python run_c2_retrieval_ablation.py --phase 1 --limit 5
uv run python run_c2_retrieval_ablation.py --phase 2 --limit 5
uv run python run_c2_retrieval_ablation.py --phase 3 --limit 5 --neighbors 1
uv run python run_c2_retrieval_ablation.py --phase all
```

## 运行

```powershell
cd <项目根>
uv sync
uv run python run_c2_retrieval_ablation.py --phase all
uv run python run_c2_retrieval_ablation.py --limit 5 --neighbors 2
uv run python run_c2_retrieval_ablation.py --no-rewrite --rerank-backend none
```

环境变量需可用的 `ARK_*`、`DEEPSEEK_*`（重排默认 `llm` 会额外调用 DeepSeek）。

## 输出

- `runs/results/c2_stage1_c1_hybrid_results.csv`
- `runs/results/c2_stage2_c1_hybrid_rerank_results.csv`
- `runs/results/c2_stage3_c1_hybrid_rerank_context_results.csv`
- `runs/results/c2_ablation_summary.json`：各组聚合指标
- `runs/results/c2_ablation_report.md`：格式化报告（便于粘贴 `experiment_notes.md`）
- `runs/logs/<组别>/run_logs.jsonl`：逐题 JSONL

CSV 在 `run_batch_experiments` 字段基础上增加：`experiment_variant`、`hybrid`、`use_rerank`、`context_neighbor_chunks`、`retrieval_query_count`、`gold_chunk_hit`、`gold_chunk_rank`、`rerank_total_tokens`。

## 指标说明（与 `docs/experiment_notes.md` 对齐）

- **预期文档命中**：`top_contains_expected_doc`，来自 `references.csv` 的 `evidence_doc_id`（可多文档逗号分隔）。
- **严格 chunk 级 Recall**：依赖 `evidence_chunk_id` **非** `pending`；当前未标全时 `gold_chunk_hit` 多为 `pending`，汇总里 chunk 召回率可能为 `null`。
- **延迟 / token**：与现有 C0/C1 批量实验同口径；`total_tokens` 为两平台用量之和，分列见 CSV 中 `volcengine_ark_total_tokens` 与 `deepseek_total_tokens`（以接口返回 `usage` 为准）。

实验完成后请将命令、模型名与 `c2_ablation_summary.json` 摘要写入 **`docs/experiment_notes.md`**（按日期与「实验运行记录模板」对齐）。**示例记录**：2026-05-06「C2 检索三阶段消融实验」（记录人：李金航）。
