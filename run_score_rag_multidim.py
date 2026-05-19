#!/usr/bin/env python3
"""Score a RAG result CSV with a multi-dimensional LLM judge.

This script is optional for experiments. It keeps the old answer-only scorer
unchanged and writes a separate ``*_llm_judged.csv`` file.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

from agentic_rag.evaluation.ai_answer_judge import judge_rag_response_with_rubric

ROOT = Path(__file__).resolve().parent
QUESTIONS_CSV = ROOT / "data" / "testset" / "questions.csv"
REFERENCES_CSV = ROOT / "data" / "testset" / "references.csv"
CHUNKS_JSONL = ROOT / "data" / "processed" / "chunks.jsonl"
DEFAULT_PROMPT = ROOT / "prompts" / "rag_multidim_judge_prompt.md"


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


def _compact(value: object, *, limit: int = 6000) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated for judge prompt]..."


def read_chunks(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    chunks: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            chunk_id = str(item.get("chunk_id") or "").strip()
            if chunk_id:
                chunks[chunk_id] = item
    return chunks


def _json_list_cell(value: str) -> list[str]:
    raw = (value or "").strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    ids: list[str] = []
    for item in parsed:
        if isinstance(item, str):
            ids.append(item)
        elif isinstance(item, dict) and item.get("chunk_id"):
            ids.append(str(item["chunk_id"]))
    return ids


def _chunk_ids_for_evidence(row: dict[str, str]) -> list[str]:
    ids: list[str] = []
    for key in (
        "final_citation_chunk_ids",
        "retrieved_chunk_ids",
        "top_chunk_ids",
        "expanded_chunk_ids",
    ):
        ids.extend(_json_list_cell(row.get(key, "")))
    out: list[str] = []
    seen: set[str] = set()
    for chunk_id in ids:
        if not chunk_id or chunk_id in seen:
            continue
        seen.add(chunk_id)
        out.append(chunk_id)
    return out


def _row_evidence(row: dict[str, str], chunks_by_id: dict[str, dict[str, Any]]) -> str:
    parts: list[str] = []
    chunk_parts: list[str] = []
    for chunk_id in _chunk_ids_for_evidence(row):
        item = chunks_by_id.get(chunk_id)
        if not item:
            continue
        doc_id = str(item.get("doc_id") or "")
        title = str(item.get("title") or "")
        text = _compact(item.get("text", ""), limit=900)
        chunk_parts.append(f"[{chunk_id}] doc_id={doc_id} title={title}\n{text}")
    if chunk_parts:
        parts.append("chunk_text:\n" + "\n\n".join(chunk_parts))

    for key in (
        "retrieved_chunks",
        "top_chunks",
        "top_doc_ids",
        "retrieved_doc_ids",
        "retrieved_chunk_ids",
    ):
        value = row.get(key)
        if value:
            parts.append(f"{key}: {_compact(value, limit=5000)}")
    return "\n\n".join(parts)


def build_multidim_parser(*, add_help: bool = True) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        add_help=add_help,
        description="Result CSV -> multi-dimensional LLM judge -> *_llm_judged.csv",
    )
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--questions", type=Path, default=QUESTIONS_CSV)
    parser.add_argument("--references", type=Path, default=REFERENCES_CSV)
    parser.add_argument("--chunks", type=Path, default=CHUNKS_JSONL)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--include-errors", action="store_true")
    return parser


def run_multidim_from_args(args: argparse.Namespace) -> None:
    questions_by_id = {
        r.get("question_id", ""): r.get("question", "")
        for r in read_csv_rows(args.questions)
    }
    refs_by_id = {r.get("question_id", ""): r for r in read_csv_rows(args.references)}
    chunks_by_id = read_chunks(args.chunks)

    rows_in = read_csv_rows(args.results)
    if args.limit > 0:
        rows_in = rows_in[: args.limit]

    extra = [
        "answer_correctness_score",
        "answer_correctness_label",
        "answer_correctness_reason",
        "answer_completeness_score",
        "answer_completeness_label",
        "answer_completeness_reason",
        "citation_accuracy_score",
        "citation_accuracy_label",
        "citation_accuracy_reason",
        "faithfulness_score",
        "faithfulness_label",
        "faithfulness_reason",
        "llm_judge_weighted_score",
        "llm_judge_failure_type",
        "llm_judge_overall_reason",
        "llm_judge_skipped",
        "llm_judge_total_tokens",
    ]
    base_fields = list(rows_in[0].keys()) if rows_in else []
    fieldnames = base_fields + [c for c in extra if c not in base_fields]

    scored_rows: list[dict[str, Any]] = []
    for row in rows_in:
        qid = row.get("question_id", "").strip()
        err = (row.get("error") or "").strip()
        out_row = dict(row)

        if err and not args.include_errors:
            out_row["llm_judge_skipped"] = "error_non_empty"
            scored_rows.append(out_row)
            continue

        ref = refs_by_id.get(qid)
        if not ref:
            out_row["llm_judge_skipped"] = "no_reference_row"
            scored_rows.append(out_row)
            continue

        try:
            jr = judge_rag_response_with_rubric(
                question=questions_by_id.get(qid, ""),
                reference_answer=ref.get("reference_answer", ""),
                generated_answer=row.get("answer", ""),
                judge_rule=ref.get("judge_rule", ""),
                retrieved_evidence=_row_evidence(row, chunks_by_id),
                generated_citations=_compact(row.get("citations", ""), limit=3000),
                gold_doc_id=ref.get("evidence_doc_id", ""),
                gold_chunk_id=ref.get("evidence_chunk_id", ""),
                prompt_file=args.prompt,
            )
        except Exception as exc:
            out_row["llm_judge_skipped"] = "judge_exception"
            out_row["llm_judge_overall_reason"] = str(exc)[:500]
            scored_rows.append(out_row)
            continue

        out_row.update(jr)
        out_row["llm_judge_skipped"] = ""
        scored_rows.append(out_row)

    out_path = args.out or (
        args.results.parent / f"{args.results.stem}_llm_judged.csv"
    )
    write_csv(out_path, fieldnames, scored_rows)
    print(f"[done] {out_path}")


def main(argv: list[str] | None = None) -> None:
    args = build_multidim_parser().parse_args(argv if argv is not None else sys.argv[1:])
    run_multidim_from_args(args)


if __name__ == "__main__":
    main()
