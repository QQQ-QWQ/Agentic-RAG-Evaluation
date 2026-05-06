# C2 检索流水线冻结快照 `snapshot_c2_pipeline_v1`

## 根因说明（为何先前「切不动」）

批量脚本每次调用 ``build_knowledge_index()`` 都会对**全部 chunk** 请求方舟 embedding；网络慢或代理环境下会在 SSL 读阶段长时间阻塞，看起来像卡住。**现已加入** ``data/processed/.kb_embedding_cache.pkl``：在 ``documents.csv`` 与源文件未变时第二次起跳过 embedding。

## 冻结包含的可运行入口（以仓库根为准）

| 文件 | 作用 |
|------|------|
| ``run_c2_retrieval_ablation.py`` | 在 **C1** 上依次跑阶段1～3（混合 / +重排 / +邻接上下文），输出 CSV、JSON、Markdown 报告 |
| ``src/agentic_rag/experiment/kb_index_builder.py`` | 切块 + 向量缓存 |
| ``src/agentic_rag/experiment/c2_ablation_metrics.py`` | 指标与 gold chunk 辅助字段 |
| ``run_batch_experiments.py`` | 已改为复用同一缓存构建索引 |

## 标准运行（必须在含 ``pyproject.toml`` 的目录）

```powershell
cd <项目根>
uv sync
uv run python run_c2_retrieval_ablation.py --phase all
```

分项调试（避免一次跑满三阶段）：

```powershell
uv run python run_c2_retrieval_ablation.py --phase 1 --limit 5
uv run python run_c2_retrieval_ablation.py --phase 2 --limit 5
uv run python run_c2_retrieval_ablation.py --phase 3 --limit 5 --neighbors 1
```

强制重建向量（慢）：

```powershell
uv run python run_c2_retrieval_ablation.py --force-rebuild-index --phase 1 --limit 3
```

## 输出（与 ``docs/experiment_notes.md`` 对齐）

- ``runs/results/c2_stage*_results.csv``
- ``runs/results/c2_ablation_summary.json``
- ``runs/results/c2_ablation_report.md``（格式化，可粘贴实验记录）

## Git 版本（填写）

```text
git_rev:
tag:
```
