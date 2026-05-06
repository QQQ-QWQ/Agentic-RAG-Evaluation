from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from agentic_rag.ark.embeddings import embed_texts
from agentic_rag.documents import parse_path
from agentic_rag.pipelines.local_rag import run_c0_with_index, run_c1_with_index
from agentic_rag.rag.simple import SimpleVectorIndex, chunk_text


ROOT = Path(__file__).resolve().parent
DOCUMENTS_CSV = ROOT / "data" / "processed" / "documents.csv"
CHUNKS_JSONL = ROOT / "data" / "processed" / "chunks.jsonl"
QUESTIONS_CSV = ROOT / "data" / "testset" / "questions.csv"
REFERENCES_CSV = ROOT / "data" / "testset" / "references.csv"
LOG_ROOT = ROOT / "runs" / "logs"
RESULT_ROOT = ROOT / "runs" / "results"

TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".csv", ".py"}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8-sig", errors="replace")


def load_document_text(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return read_text_file(file_path)
    return parse_path(file_path).text


def build_knowledge_index(
    documents_csv: Path = DOCUMENTS_CSV,
    chunks_jsonl: Path = CHUNKS_JSONL,
) -> SimpleVectorIndex:
    documents = read_csv_rows(documents_csv)
    chunks: list[str] = []
    metadata: list[dict[str, Any]] = []

    for row in documents:
        file_path = (ROOT / row["file_path"]).resolve()
        if not file_path.is_file():
            print(f"[WARN] skip missing document: {row['file_path']}")
            continue

        raw_text = load_document_text(file_path)
        doc_text = "\n".join(
            [
                f"Document ID: {row['doc_id']}",
                f"Title: {row.get('title', '')}",
                f"Document Type: {row.get('doc_type', '')}",
                f"Source Note: {row.get('source', '')}",
                "",
                raw_text,
            ]
        )
        doc_chunks = chunk_text(doc_text, chunk_size=500, overlap=80)
        for chunk_index, chunk in enumerate(doc_chunks):
            chunks.append(chunk)
            metadata.append(
                {
                    "chunk_id": f"{row['doc_id']}::chunk_{chunk_index:04d}",
                    "doc_id": row["doc_id"],
                    "title": row.get("title", ""),
                    "source": str(file_path),
                    "relative_path": row["file_path"],
                    "doc_type": row.get("doc_type", ""),
                    "chunk_index": chunk_index,
                    "page": None,
                }
            )

    if not chunks:
        raise ValueError("No document chunks were built from data/processed/documents.csv")

    chunks_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with chunks_jsonl.open("w", encoding="utf-8") as f:
        for chunk, meta in zip(chunks, metadata, strict=True):
            f.write(
                json.dumps(
                    {
                        **meta,
                        "text": chunk,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    vectors = embed_texts(chunks, is_query=False)
    index = SimpleVectorIndex(chunks=chunks, vectors=vectors)
    index.doc_id = "knowledge_base"
    index.source = str(documents_csv)
    index.chunk_metadata = metadata
    return index


def backup_and_reset_log(config_name: str) -> Path:
    log_dir = LOG_ROOT / config_name
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "run_logs.jsonl"
    if log_path.exists() and log_path.stat().st_size > 0:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = log_dir / f"run_logs.before_batch_{stamp}.jsonl"
        shutil.copy2(log_path, backup_path)
    log_path.write_text("", encoding="utf-8")
    return log_path


def token_total(result: dict[str, Any]) -> int:
    usage = result.get("token_usage") or {}
    total = 0
    for value in usage.values():
        if isinstance(value, dict):
            total += int(value.get("total_tokens") or 0)
    return total


def expected_doc_ids(ref_row: dict[str, str] | None) -> list[str]:
    if not ref_row:
        return []
    raw = ref_row.get("evidence_doc_id", "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def top_rank_expected_doc(
    result: dict[str, Any],
    expected_docs: list[str],
) -> int | str:
    if not expected_docs:
        return ""
    for rank, hit in enumerate(result.get("retrieved_chunks") or [], start=1):
        if str(hit.get("doc_id", "")) in expected_docs:
            return rank
    return ""


def result_to_row(
    result: dict[str, Any],
    question_row: dict[str, str],
    reference_row: dict[str, str] | None,
) -> dict[str, Any]:
    hits = result.get("retrieved_chunks") or []
    citations = result.get("citations") or []
    expected_docs = expected_doc_ids(reference_row)
    first_expected_rank = top_rank_expected_doc(result, expected_docs)

    rewrite_usage = (result.get("token_usage") or {}).get("query_rewrite") or {}
    answer_usage = (result.get("token_usage") or {}).get("answer_generation") or {}

    return {
        "question_id": question_row.get("question_id", ""),
        "config": result.get("config", ""),
        "task_type": question_row.get("task_type", ""),
        "difficulty": question_row.get("difficulty", ""),
        "required_tool": question_row.get("required_tool", ""),
        "expected_path": question_row.get("expected_path", ""),
        "error": result.get("error", ""),
        "latency_ms": result.get("latency_ms", ""),
        "expected_doc_ids": json.dumps(expected_docs, ensure_ascii=False),
        "top_contains_expected_doc": bool(first_expected_rank != ""),
        "top_rank_expected_doc": first_expected_rank,
        "top_chunk_ids": json.dumps(
            [hit.get("chunk_id", "") for hit in hits],
            ensure_ascii=False,
        ),
        "top_doc_ids": json.dumps(
            [hit.get("doc_id", "") for hit in hits],
            ensure_ascii=False,
        ),
        "citations": json.dumps(citations, ensure_ascii=False),
        "answer": result.get("answer", ""),
        "need_rewrite": result.get("need_rewrite", ""),
        "rewritten_query": result.get("rewritten_query", ""),
        "rewrite_reason": result.get("rewrite_reason", ""),
        "rewrite_type": result.get("rewrite_type", ""),
        "query_rewrite_tokens": rewrite_usage.get("total_tokens", ""),
        "answer_tokens": answer_usage.get("total_tokens", ""),
        "total_tokens": token_total(result),
        "log_path": result.get("log_path", ""),
    }


def write_results_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
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
        "rewritten_query",
        "rewrite_reason",
        "rewrite_type",
        "query_rewrite_tokens",
        "answer_tokens",
        "total_tokens",
        "log_path",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_config(
    config_name: str,
    index: SimpleVectorIndex,
    questions: list[dict[str, str]],
    references: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    backup_and_reset_log(config_name)
    rows: list[dict[str, Any]] = []
    for i, question_row in enumerate(questions, start=1):
        qid = question_row.get("question_id", "")
        question = question_row.get("question", "")
        print(f"[{config_name}] {i}/{len(questions)} {qid}")
        common_kwargs = {
            "question_id": qid,
            "top_k": 5,
            "log_dir": LOG_ROOT,
            "hybrid": False,
            "use_rerank": False,
            "context_neighbor_chunks": 0,
        }
        if config_name == "c0_naive":
            result = run_c0_with_index(index, question, **common_kwargs)
        elif config_name == "c1_rewrite":
            result = run_c1_with_index(index, question, **common_kwargs)
        else:
            raise ValueError(f"Unsupported config: {config_name}")
        rows.append(result_to_row(result, question_row, references.get(qid)))
    return rows


def main() -> None:
    print("[index] building shared knowledge index")
    index = build_knowledge_index()
    questions = read_csv_rows(QUESTIONS_CSV)[:20]
    references = {
        row.get("question_id", ""): row for row in read_csv_rows(REFERENCES_CSV)
    }

    c0_rows = run_config("c0_naive", index, questions, references)
    write_results_csv(RESULT_ROOT / "c0_results.csv", c0_rows)

    c1_rows = run_config("c1_rewrite", index, questions, references)
    write_results_csv(RESULT_ROOT / "c1_results.csv", c1_rows)

    print("[done] wrote:")
    print(f"- {LOG_ROOT / 'c0_naive' / 'run_logs.jsonl'}")
    print(f"- {RESULT_ROOT / 'c0_results.csv'}")
    print(f"- {LOG_ROOT / 'c1_rewrite' / 'run_logs.jsonl'}")
    print(f"- {RESULT_ROOT / 'c1_results.csv'}")


if __name__ == "__main__":
    main()
