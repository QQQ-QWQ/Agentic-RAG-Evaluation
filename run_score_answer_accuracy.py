#!/usr/bin/env python3
"""单份结果 CSV：按 references.csv 的 judge_rule 评判答案，写出 *_scored.csv。"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

from agentic_rag.evaluation.ai_answer_judge import judge_answer_with_rule

ROOT = Path(__file__).resolve().parent
QUESTIONS_CSV = ROOT / "data" / "testset" / "questions.csv"
REFERENCES_CSV = ROOT / "data" / "testset" / "references.csv"
DEFAULT_PROMPT = ROOT / "prompts" / "answer_judge_prompt.md"


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


def build_score_answer_parser(*, add_help: bool = True) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        add_help=add_help,
        description="单份结果 CSV → LLM 评判 → *_scored.csv",
    )
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--questions", type=Path, default=QUESTIONS_CSV)
    parser.add_argument("--references", type=Path, default=REFERENCES_CSV)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--include-errors", action="store_true")
    return parser


def run_score_answer_from_args(args: argparse.Namespace) -> None:
    questions_by_id = {
        r.get("question_id", ""): r.get("question", "")
        for r in read_csv_rows(args.questions)
    }
    refs_by_id = {r.get("question_id", ""): r for r in read_csv_rows(args.references)}

    rows_in = read_csv_rows(args.results)
    if args.limit > 0:
        rows_in = rows_in[: args.limit]

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
    for row in rows_in:
        qid = row.get("question_id", "").strip()
        err = (row.get("error") or "").strip()
        out_row = dict(row)

        if err and not args.include_errors:
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
                prompt_file=args.prompt,
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
        scored_rows.append(out_row)

    out_path = args.out or (args.results.parent / f"{args.results.stem}_scored.csv")
    write_csv(out_path, fieldnames, scored_rows)
    print(f"[done] {out_path}")


def main(argv: list[str] | None = None) -> None:
    args = build_score_answer_parser().parse_args(argv if argv is not None else sys.argv[1:])
    run_score_answer_from_args(args)


if __name__ == "__main__":
    main()
