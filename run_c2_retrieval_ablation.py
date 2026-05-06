#!/usr/bin/env python3
"""
C2 检索实验：在 **C1（query rewrite）** 基础上依次叠加三项能力并分别评测：

| 阶段 | 含义 |
|------|------|
| 1 | C1 + **混合检索**（稠密 + BM25） |
| 2 | C1 + 混合检索 + **LLM 重排**（可用 ``--rerank-backend none`` 对照） |
| 3 | C1 + 混合检索 + 重排 + **邻接上下文补全** |

一次索引构建后跑多个阶段；向量索引默认写入 ``data/processed/.kb_embedding_cache.pkl``，
避免每次全量调用方舟 embedding 长时间卡住（终端常见卡在 SSL read）。

用法::

    cd <含 pyproject.toml 的项目根>
    uv sync
    uv run python run_c2_retrieval_ablation.py --phase all
    uv run python run_c2_retrieval_ablation.py --phase 1 --limit 5
    uv run python run_c2_retrieval_ablation.py --force-rebuild-index

勿用系统自带的 Python 直接运行（缺 editable 包）；务必 ``uv run python``。
"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 允许在未配置 uv 时从仓库根运行：将 src 加入路径（仍以 uv 为准）
_REPO_ROOT = Path(__file__).resolve().parent
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agentic_rag.experiment.c2_ablation_metrics import (  # noqa: E402
    row_extend_ablation,
    summarize_variant,
)
from agentic_rag.pipelines.local_rag import run_c0_with_index, run_c1_with_index  # noqa: E402
from agentic_rag.rag.simple import SimpleVectorIndex  # noqa: E402

from run_batch_experiments import (  # noqa: E402
    C1_PROMPT,
    LOG_ROOT,
    QUESTIONS_CSV,
    REFERENCES_CSV,
    RESULT_ROOT,
    backup_and_reset_log,
    build_knowledge_index,
    read_csv_rows,
    result_to_row,
)

EXTENDED_FIELDS = [
    "question_id",
    "config",
    "task_type",
    "difficulty",
    "required_tool",
    "expected_path",
    "error",
    "latency_ms",
    "expected_doc_ids",
    "top_contains_expected_doc",
    "top_rank_expected_doc",
    "top_chunk_ids",
    "top_doc_ids",
    "citations",
    "answer",
    "need_rewrite",
    "rewrite_confidence",
    "rewritten_query",
    "rewritten_queries",
    "rewrite_reason",
    "rewrite_type",
    "query_rewrite_tokens",
    "deepseek_rerank_tokens",
    "answer_tokens",
    "volcengine_ark_total_tokens",
    "deepseek_total_tokens",
    "query_rewrite_model_response",
    "total_tokens",
    "log_path",
    "experiment_variant",
    "hybrid",
    "use_rerank",
    "context_neighbor_chunks",
    "retrieval_query_count",
    "gold_chunk_hit",
    "gold_chunk_rank",
    "rerank_total_tokens",
]

# 在 C1 上依次加能力：与 ``docs/experiment_notes`` 中 C2 定位一致
VARIANTS: list[tuple[str, str, bool, bool, int, str]] = [
    (
        "c2_stage1_c1_hybrid",
        "阶段1：C1+混合检索",
        True,
        False,
        0,
        "仅打开混合检索；无重排、无邻接扩展。",
    ),
    (
        "c2_stage2_c1_hybrid_rerank",
        "阶段2：C1+混合+重排",
        True,
        True,
        0,
        "在阶段1基础上打开检索后重排。",
    ),
    (
        "c2_stage3_c1_hybrid_rerank_context",
        "阶段3：C1+混合+重排+上下文补全",
        True,
        True,
        0,  # neighbors 由 args 覆盖
        "在阶段2基础上对命中块做 ±N 邻接扩展后生成。",
    ),
]


def write_extended_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=EXTENDED_FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            out = {k: row.get(k, "") for k in EXTENDED_FIELDS}
            w.writerow(out)


def run_variant(
    *,
    variant_key: str,
    display_name: str,
    index: SimpleVectorIndex,
    questions: list[dict[str, str]],
    references: dict[str, dict[str, str]],
    use_rewrite: bool,
    hybrid: bool,
    use_rerank: bool,
    context_neighbor_chunks: int,
    top_k: int,
    rerank_backend: str,
    rerank_pool_size: int,
    dense_weight: float,
    bm25_weight: float,
) -> list[dict[str, Any]]:
    backup_and_reset_log(variant_key)
    rows_out: list[dict[str, Any]] = []
    common = {
        "top_k": top_k,
        "log_dir": LOG_ROOT,
        "hybrid": hybrid,
        "dense_weight": dense_weight,
        "bm25_weight": bm25_weight,
        "use_rerank": use_rerank,
        "rerank_backend": rerank_backend,
        "rerank_pool_size": rerank_pool_size,
        "context_neighbor_chunks": context_neighbor_chunks,
    }
    for i, question_row in enumerate(questions, start=1):
        qid = question_row.get("question_id", "")
        question = question_row.get("question", "")
        print(f"[{display_name}] {i}/{len(questions)} {qid}")
        if use_rewrite:
            result = run_c1_with_index(
                index,
                question,
                prompt_file=C1_PROMPT,
                question_id=qid,
                **common,
            )
        else:
            result = run_c0_with_index(
                index,
                question,
                question_id=qid,
                **common,
            )
        patched = deepcopy(result)
        patched["config"] = variant_key
        ref = references.get(qid)
        base_row = result_to_row(patched, question_row, ref)
        row = row_extend_ablation(
            base_row,
            variant_name=variant_key,
            hybrid=hybrid,
            use_rerank=use_rerank,
            context_neighbor_chunks=context_neighbor_chunks,
            result=result,
            reference_row=ref,
        )
        rows_out.append(row)
    return rows_out


def write_markdown_report(
    path: Path,
    summary: dict[str, Any],
    variant_defs: list[tuple[str, str, bool, bool, int, str]],
    neighbors_used: int,
) -> None:
    lines = [
        "# C2 检索实验报告（基于 C1 依次叠加）",
        "",
        f"- 生成时间（UTC）：{datetime.now(timezone.utc).isoformat()}",
        f"- 阶段3邻接参数 neighbors：**{neighbors_used}**",
        "",
        "## 配置说明",
        "",
        "| 阶段 key | 说明 |",
        "| --- | --- |",
    ]
    for key, label, hy, rr, _n, desc in variant_defs:
        lines.append(f"| `{key}` | {label} — {desc} |")
    lines.extend(
        [
            "",
            "## 汇总指标",
            "",
            "| 阶段 | 题数 | 错误 | 文档命中 | 命中率 | 均延迟(ms) | 均token | 均检索query数 | chunk可评 | chunk召回 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for key, _, _, _, _, _ in variant_defs:
        s = summary["variants"].get(key, {})
        n = s.get("n_questions", 0)
        dr = s.get("expected_doc_hit_rate")
        dr_pct = f"{100 * dr:.1f}%" if dr is not None else ""
        ml = s.get("mean_latency_ms")
        ml_s = f"{ml:.0f}" if isinstance(ml, (int, float)) else ""
        mt = s.get("mean_total_tokens")
        mt_s = f"{mt:.0f}" if isinstance(mt, (int, float)) else ""
        mr = s.get("mean_retrieval_query_count")
        mr_s = f"{mr:.2f}" if isinstance(mr, (int, float)) else ""
        gcr = s.get("gold_chunk_recall_rate")
        gcr_s = f"{100 * gcr:.1f}%" if gcr is not None else "—"
        ge = s.get("gold_chunk_hit_count", 0) + s.get("gold_chunk_miss_count", 0)
        lines.append(
            f"| {key} | {n} | {s.get('error_count', '')} | "
            f"{s.get('expected_doc_hit_count', '')}/{n} | {dr_pct} | {ml_s} | {mt_s} | {mr_s} | {ge} | {gcr_s} |"
        )
    lines.extend(
        [
            "",
            "> `evidence_chunk_id` 全为 pending 时 chunk 召回列填 —。",
            "",
            "## 机器可读摘要",
            "",
            "```json",
            json.dumps(summary, ensure_ascii=False, indent=2),
            "```",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="C2：在 C1 上依次测试 混合检索 → +重排 → +上下文补全",
    )
    parser.add_argument(
        "--phase",
        choices=["1", "2", "3", "all"],
        default="all",
        help="只跑某一阶段或全部（默认 all）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="测试题条数上限（默认 20）",
    )
    parser.add_argument(
        "--neighbors",
        type=int,
        default=1,
        help="阶段3：每条命中向两侧扩展的切块数（默认 1）",
    )
    parser.add_argument(
        "--no-rewrite",
        action="store_true",
        help="不用 C1，三条均走 C0（仅当你要做纯检索对照时）",
    )
    parser.add_argument("--top-k", type=int, default=5, metavar="K")
    parser.add_argument("--rerank-pool", type=int, default=20, metavar="N")
    parser.add_argument(
        "--rerank-backend",
        default="llm",
        choices=["llm", "none"],
        help="阶段2/3 重排：llm 调 DeepSeek；none 不调 API（分数截断）",
    )
    parser.add_argument("--dense-weight", type=float, default=0.6)
    parser.add_argument("--bm25-weight", type=float, default=0.4)
    parser.add_argument(
        "--force-rebuild-index",
        action="store_true",
        help="忽略本地向量缓存，强制重新调用方舟 embedding（慢）",
    )
    parser.add_argument(
        "--no-index-cache",
        action="store_true",
        help="不使用向量缓存文件（仍可做单次全量 embedding）",
    )
    args = parser.parse_args()

    use_rewrite = not args.no_rewrite

    phase_filter = {"1": {0}, "2": {1}, "3": {2}, "all": {0, 1, 2}}[args.phase]
    neighbors = max(0, args.neighbors)

    selected: list[tuple[str, str, bool, bool, int, str]] = []
    for i, row in enumerate(VARIANTS):
        if i not in phase_filter:
            continue
        key, title, hy, rr, n0, desc = row
        if i == 2:
            # 阶段3 使用 CLI neighbors
            selected.append((key, title, hy, rr, neighbors, desc))
        else:
            selected.append((key, title, hy, rr, n0, desc))

    print(
        "[index] 构建知识库向量索引（有缓存则秒开）…\n"
        "        若首次运行会调用方舟 embedding，请勿中断；完成后自动生成缓存。"
    )
    index = build_knowledge_index(
        use_cache=not args.no_index_cache,
        force_rebuild=args.force_rebuild_index,
    )

    questions = read_csv_rows(QUESTIONS_CSV)[: max(1, args.limit)]
    references = {
        row.get("question_id", ""): row for row in read_csv_rows(REFERENCES_CSV)
    }

    summary: dict[str, Any] = {
        "phase": args.phase,
        "limit": args.limit,
        "use_query_rewrite": use_rewrite,
        "top_k": args.top_k,
        "rerank_pool_size": args.rerank_pool,
        "rerank_backend": args.rerank_backend,
        "dense_weight": args.dense_weight,
        "bm25_weight": args.bm25_weight,
        "neighbors_stage3": neighbors,
        "index_cache": {
            "disabled": args.no_index_cache,
            "force_rebuild": args.force_rebuild_index,
        },
        "variants": {},
    }

    out_paths: list[str] = []

    for key, label, hybrid, rerank, ctx_neighbors, _desc in selected:
        rows = run_variant(
            variant_key=key,
            display_name=label,
            index=index,
            questions=questions,
            references=references,
            use_rewrite=use_rewrite,
            hybrid=hybrid,
            use_rerank=rerank,
            context_neighbor_chunks=ctx_neighbors,
            top_k=args.top_k,
            rerank_backend=args.rerank_backend,
            rerank_pool_size=args.rerank_pool,
            dense_weight=args.dense_weight,
            bm25_weight=args.bm25_weight,
        )
        csv_path = RESULT_ROOT / f"{key}_results.csv"
        write_extended_csv(csv_path, rows)
        out_paths.append(str(csv_path))
        summary["variants"][key] = summarize_variant(rows)

    summary_path = RESULT_ROOT / "c2_ablation_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report_path = RESULT_ROOT / "c2_ablation_report.md"
    write_markdown_report(report_path, summary, selected, neighbors)

    print("\n[done] 输出：")
    for p in out_paths:
        print(f"  - {p}")
    print(f"  - {summary_path}")
    print(f"  - {report_path}")

    print("\n### 摘要预览\n")
    print("| 阶段 | 题数 | 错误 | 文档命中 | 命中率 | 均延迟(ms) | 均token |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for key, _, _, _, _, _ in selected:
        s = summary["variants"][key]
        n = s.get("n_questions", 0)
        dr = s.get("expected_doc_hit_rate")
        dr_pct = f"{100 * dr:.1f}%" if dr is not None else ""
        ml = s.get("mean_latency_ms")
        ml_s = f"{ml:.0f}" if isinstance(ml, (int, float)) else ""
        mt = s.get("mean_total_tokens")
        mt_s = f"{mt:.0f}" if isinstance(mt, (int, float)) else ""
        print(
            f"| {key} | {n} | {s.get('error_count', '')} | "
            f"{s.get('expected_doc_hit_count', '')}/{n} | {dr_pct} | {ml_s} | {mt_s} |"
        )


if __name__ == "__main__":
    main()
