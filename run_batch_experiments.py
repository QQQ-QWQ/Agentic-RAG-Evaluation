from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from agentic_rag.experiment.kb_index_builder import load_or_build_knowledge_index
from agentic_rag.pipelines.local_rag import run_c0_with_index, run_c1_with_index
from agentic_rag.rag.simple import SimpleVectorIndex


ROOT = Path(__file__).resolve().parent
DOCUMENTS_CSV = ROOT / "data" / "processed" / "documents.csv"
CHUNKS_JSONL = ROOT / "data" / "processed" / "chunks.jsonl"
QUESTIONS_CSV = ROOT / "data" / "testset" / "questions.csv"
REFERENCES_CSV = ROOT / "data" / "testset" / "references.csv"
C1_PROMPT = ROOT / "prompts" / "query_rewrite_prompt.md"
LOG_ROOT = ROOT / "runs" / "logs"
RESULT_ROOT = ROOT / "runs" / "results"

def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def build_knowledge_index(
    documents_csv: Path = DOCUMENTS_CSV,
    chunks_jsonl: Path = CHUNKS_JSONL,
    *,
    use_cache: bool = True,
    force_rebuild: bool = False,
) -> SimpleVectorIndex:
    """构建共享知识库索引；默认使用 ``data/processed/.kb_embedding_cache.pkl`` 跳过重复 embedding。"""
    return load_or_build_knowledge_index(
        ROOT,
        documents_csv=documents_csv,
        chunks_jsonl=chunks_jsonl,
        use_cache=use_cache,
        force_rebuild=force_rebuild,
    )


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


def volcengine_ark_token_total(result: dict[str, Any]) -> int:
    """火山方舟（embedding）侧 total_tokens，仅统计 ``ark_volcengine_embedding``。"""
    u = (result.get("token_usage") or {}).get("ark_volcengine_embedding") or {}
    if not isinstance(u, dict) or u.get("total_tokens") is None:
        return 0
    try:
        return int(u["total_tokens"])
    except (TypeError, ValueError):
        return 0


def deepseek_token_total(result: dict[str, Any]) -> int:
    """DeepSeek 侧合计：改写 + 重排 + 答案生成（各槽位 ``total_tokens`` 相加）。"""
    tu = result.get("token_usage") or {}
    total = 0
    for key in ("query_rewrite", "rerank", "answer_generation"):
        slot = tu.get(key) or {}
        if isinstance(slot, dict) and slot.get("total_tokens") is not None:
            try:
                total += int(slot["total_tokens"])
            except (TypeError, ValueError):
                pass
    return total


def token_total(result: dict[str, Any]) -> int:
    """两平台用量之和（方舟 embedding + DeepSeek 各调用）。"""
    return volcengine_ark_token_total(result) + deepseek_token_total(result)


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

    tu = result.get("token_usage") or {}
    rewrite_usage = tu.get("query_rewrite") or {}
    answer_usage = tu.get("answer_generation") or {}
    rerank_usage = tu.get("rerank") or {}
    rw_raw = result.get("query_rewrite_model_raw") or ""
    if len(rw_raw) > 15000:
        rw_raw = rw_raw[:15000] + "\n...[truncated]"

    return {
        "question_id": question_row.get("question_id", ""),
        "config": result.get("config", ""),
        "task_type": question_row.get("task_type", ""),
        "difficulty": question_row.get("difficulty", ""),
        "required_tool": question_row.get("required_tool", ""),
        "expected_path": question_row.get("expected_path", ""),
        "error": result.get("error", ""),
        "latency_ms": result.get("latency_ms", ""),
        "retrieval_query_count": len(result.get("retrieval_queries") or []),
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
        "rewrite_confidence": result.get("rewrite_confidence", ""),
        "rewritten_query": result.get("rewritten_query", ""),
        "rewritten_queries": json.dumps(
            result.get("rewritten_queries", []),
            ensure_ascii=False,
        ),
        "rewrite_reason": result.get("rewrite_reason", ""),
        "rewrite_type": result.get("rewrite_type", ""),
        "query_rewrite_tokens": rewrite_usage.get("total_tokens", ""),
        "deepseek_rerank_tokens": rerank_usage.get("total_tokens", ""),
        "answer_tokens": answer_usage.get("total_tokens", ""),
        "volcengine_ark_total_tokens": volcengine_ark_token_total(result),
        "deepseek_total_tokens": deepseek_token_total(result),
        "query_rewrite_model_response": rw_raw,
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
        "retrieval_query_count",
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
            result = run_c1_with_index(
                index,
                question,
                prompt_file=C1_PROMPT,
                **common_kwargs,
            )
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
