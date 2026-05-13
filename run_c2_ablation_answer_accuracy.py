#!/usr/bin/env python3
"""
对 C2 三份阶段结果 CSV 依次调用 LLM 评判（与 references.csv 的 judge_rule 对齐），
并生成汇总 JSON / Markdown；指标口径对齐 experiment_notes 中赵启行「批量实验」表格，
并补充答案正确率（0/0.5/1）。

说明：仓库当前仅有 C2 检索三阶段消融产物；若口语中说「C3 三次消融」，在无 C3 CSV 时
请先按本脚本的 C2 三阶段理解。

用法::

    uv run python run_c2_ablation_answer_accuracy.py
    uv run python run_c2_ablation_answer_accuracy.py --skip-judge   # 仅基于已有 *_scored.csv 汇总
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from agentic_rag.evaluation.ai_answer_judge import judge_answer_with_rule

ROOT = Path(__file__).resolve().parent
QUESTIONS_CSV = ROOT / "data" / "testset" / "questions.csv"
REFERENCES_CSV = ROOT / "data" / "testset" / "references.csv"
PROMPT_PATH = ROOT / "prompts" / "answer_judge_prompt.md"
RESULT_DIR = ROOT / "runs" / "results"

VARIANTS: list[tuple[str, Path]] = [
    ("阶段1：C1+混合检索", RESULT_DIR / "c2_stage1_c1_hybrid_results.csv"),
    ("阶段2：C1+混合+重排", RESULT_DIR / "c2_stage2_c1_hybrid_rerank_results.csv"),
    ("阶段3：C1+混合+重排+上下文", RESULT_DIR / "c2_stage3_c1_hybrid_rerank_context_results.csv"),
]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def _truthy_doc_hit(v: object) -> bool:
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s in ("true", "1", "yes")


def _float_cell(row: dict[str, str], key: str) -> float | None:
    raw = row.get(key)
    if raw in ("", None):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def score_one_csv(
    *,
    label: str,
    results_path: Path,
    questions_by_id: dict[str, str],
    refs_by_id: dict[str, dict[str, str]],
    prompt_path: Path,
    skip_judge: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """返回 scored 行列表与摘要 dict。"""
    if not results_path.is_file():
        raise FileNotFoundError(f"缺少结果文件: {results_path}")

    scored_path = results_path.parent / f"{results_path.stem}_scored.csv"
    rows_in = read_csv_rows(results_path)

    extra = [
        "correctness_score",
        "correctness_label",
        "judge_reason",
        "judge_skipped",
        "judge_total_tokens",
    ]
    base_fields = list(rows_in[0].keys()) if rows_in else []
    fieldnames = base_fields + [c for c in extra if c not in base_fields]

    scored_rows: list[dict[str, Any]] = []
    judge_tokens_sum = 0

    if skip_judge and scored_path.is_file():
        scored_rows = [dict(r) for r in read_csv_rows(scored_path)]
        for r in scored_rows:
            jt = r.get("judge_total_tokens", "")
            if str(jt).strip().isdigit():
                judge_tokens_sum += int(jt)
    else:
        for row in rows_in:
            qid = row.get("question_id", "").strip()
            err = (row.get("error") or "").strip()
            out_row = dict(row)

            if err:
                out_row["correctness_score"] = ""
                out_row["correctness_label"] = ""
                out_row["judge_reason"] = ""
                out_row["judge_skipped"] = "error_non_empty"
                out_row["judge_total_tokens"] = ""
                scored_rows.append(out_row)
                continue

            ref = refs_by_id.get(qid)
            if not ref:
                out_row["correctness_score"] = ""
                out_row["correctness_label"] = ""
                out_row["judge_reason"] = ""
                out_row["judge_skipped"] = "no_reference_row"
                out_row["judge_total_tokens"] = ""
                scored_rows.append(out_row)
                continue

            qtext = (questions_by_id.get(qid) or "").strip()
            try:
                jr = judge_answer_with_rule(
                    question=qtext,
                    reference_answer=ref.get("reference_answer", ""),
                    generated_answer=row.get("answer", ""),
                    judge_rule=ref.get("judge_rule", ""),
                    prompt_file=prompt_path,
                )
            except Exception as exc:
                out_row["correctness_score"] = ""
                out_row["correctness_label"] = ""
                out_row["judge_reason"] = str(exc)[:500]
                out_row["judge_skipped"] = "judge_exception"
                out_row["judge_total_tokens"] = ""
                scored_rows.append(out_row)
                continue

            out_row["correctness_score"] = jr["correctness_score"]
            out_row["correctness_label"] = jr["correctness_label"]
            out_row["judge_reason"] = jr["judge_reason"]
            out_row["judge_skipped"] = ""
            out_row["judge_total_tokens"] = jr["judge_total_tokens"]
            judge_tokens_sum += int(jr["judge_total_tokens"])
            scored_rows.append(out_row)

        write_csv(scored_path, fieldnames, scored_rows)
        print(f"[judge] {label} -> {scored_path}")

    # --- 摘要（对齐赵启行：文档级命中、延迟、token、检索 query 数）---
    n = len(scored_rows)
    doc_hits = sum(1 for r in scored_rows if _truthy_doc_hit(r.get("top_contains_expected_doc")))
    miss_ids = [
        r.get("question_id", "")
        for r in scored_rows
        if r.get("question_id") and not _truthy_doc_hit(r.get("top_contains_expected_doc"))
    ]
    latencies = [
        x for r in scored_rows if (x := _float_cell(r, "latency_ms")) is not None
    ]
    tokens_rag = [
        x for r in scored_rows if (x := _float_cell(r, "total_tokens")) is not None
    ]
    rq_counts = [
        x for r in scored_rows if (x := _float_cell(r, "retrieval_query_count")) is not None
    ]

    scores: list[float] = []
    for r in scored_rows:
        if r.get("judge_skipped"):
            continue
        try:
            s = float(r.get("correctness_score", ""))
        except (TypeError, ValueError):
            continue
        scores.append(s)

    full_n = sum(1 for s in scores if s >= 1.0 - 1e-9)
    partial_n = sum(1 for s in scores if abs(s - 0.5) < 1e-6)
    wrong_n = sum(1 for s in scores if s < 0.25)
    dist = Counter(scores)
    summary = {
        "label": label,
        "csv": str(results_path),
        "scored_csv": str(scored_path),
        "n_questions": n,
        "expected_doc_hit_count": doc_hits,
        "expected_doc_hit_rate": doc_hits / n if n else 0.0,
        "miss_question_ids": miss_ids,
        "mean_latency_ms": sum(latencies) / len(latencies) if latencies else None,
        "mean_total_tokens": sum(tokens_rag) / len(tokens_rag) if tokens_rag else None,
        "mean_retrieval_query_count": sum(rq_counts) / len(rq_counts) if rq_counts else None,
        "answer_correctness_mean": sum(scores) / len(scores) if scores else None,
        "answer_correctness_full_count": full_n,
        "answer_correctness_partial_count": partial_n,
        "answer_correctness_wrong_count": wrong_n,
        "answer_correctness_distribution": {str(k): v for k, v in sorted(dist.items())},
        "judge_total_tokens_sum": judge_tokens_sum,
        "judge_prompt": str(prompt_path),
    }
    return scored_rows, summary


def build_c2_accuracy_parser(*, add_help: bool = True) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        add_help=add_help,
        description="C2 三阶段答案正确率 + 检索口径汇总",
    )
    parser.add_argument("--questions", type=Path, default=QUESTIONS_CSV)
    parser.add_argument("--references", type=Path, default=REFERENCES_CSV)
    parser.add_argument("--prompt", type=Path, default=PROMPT_PATH)
    parser.add_argument(
        "--skip-judge",
        action="store_true",
        help="不调用 API，仅读取已存在的 *_scored.csv 做汇总",
    )
    return parser


def run_c2_ablation_accuracy_from_args(args: argparse.Namespace) -> None:
    questions_by_id = {
        r.get("question_id", ""): r.get("question", "")
        for r in read_csv_rows(args.questions)
    }
    refs_by_id = {r.get("question_id", ""): r for r in read_csv_rows(args.references)}

    all_summaries: list[dict[str, Any]] = []
    for label, path in VARIANTS:
        _, summ = score_one_csv(
            label=label,
            results_path=path,
            questions_by_id=questions_by_id,
            refs_by_id=refs_by_id,
            prompt_path=args.prompt,
            skip_judge=args.skip_judge,
        )
        all_summaries.append(summ)

    out_json = RESULT_DIR / "c2_ablation_answer_accuracy.json"
    out_md = RESULT_DIR / "c2_ablation_answer_accuracy_report.md"
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    def _rel(p: Path) -> str:
        try:
            return p.resolve().relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            return str(p)

    variants_obj: dict[str, Any] = {}
    for s in all_summaries:
        key = _rel(Path(s["csv"]))
        entry = dict(s)
        entry["csv"] = _rel(Path(s["csv"]))
        entry["scored_csv"] = _rel(Path(s["scored_csv"]))
        entry["judge_prompt"] = _rel(Path(s["judge_prompt"]))
        variants_obj[key] = entry

    payload = {
        "note": (
            "指标说明：文档级命中/延迟/total_tokens/retrieval_query_count 来自各阶段 CSV；"
            "答案得分由 DeepSeek 按 references.csv 的 judge_rule 评判（0/0.5/1）。"
            "对齐 experiment_notes 赵启行批量表，并补充 Answer Correctness。"
        ),
        "variants": variants_obj,
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# C2 三阶段消融：答案正确率与检索口径汇总",
        "",
        "> 与 `docs/experiment_notes.md` 中赵启行「批量运行结果」表格同一口径（文档级命中、均延迟、均 token、均检索 query 数），",
        "> 并补充 **LLM 评判** 的满分条数 / 部分对 / 错误及平均分。",
        "",
        "| 阶段 | 文档级命中 | 未命中题 | 满分(1.0) | 部分对(0.5) | 错误(0) | 平均得分 | 均延迟(ms) | 均 total_tokens | 均检索 query 数 | 评判消耗 token |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for s in all_summaries:
        miss = "、".join(s["miss_question_ids"]) if s["miss_question_ids"] else "—"
        ml = s["mean_latency_ms"]
        ml_s = f"{ml:.0f}" if isinstance(ml, (int, float)) else "—"
        mt = s["mean_total_tokens"]
        mt_s = f"{mt:.0f}" if isinstance(mt, (int, float)) else "—"
        mr = s["mean_retrieval_query_count"]
        mr_s = f"{mr:.2f}" if isinstance(mr, (int, float)) else "—"
        ma = s["answer_correctness_mean"]
        ma_s = f"{ma:.3f}" if isinstance(ma, (int, float)) else "—"
        lines.append(
            f"| {s['label']} | {s['expected_doc_hit_count']}/{s['n_questions']} | {miss} | "
            f"{s['answer_correctness_full_count']} | {s['answer_correctness_partial_count']} | "
            f"{s['answer_correctness_wrong_count']} | {ma_s} | {ml_s} | {mt_s} | {mr_s} | "
            f"{s['judge_total_tokens_sum']} |"
        )
    try:
        json_rel = out_json.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        json_rel = out_json.name
    lines.extend(
        [
            "",
            f"- 详细 JSON：`{json_rel}`",
            "- 逐题评分 CSV：各阶段结果同目录 `*_scored.csv`",
            "",
        ]
    )
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"[done] {out_json}")
    print(f"[done] {out_md}")


def main(argv: list[str] | None = None) -> None:
    args = build_c2_accuracy_parser().parse_args(argv if argv is not None else sys.argv[1:])
    run_c2_ablation_accuracy_from_args(args)


if __name__ == "__main__":
    main()
