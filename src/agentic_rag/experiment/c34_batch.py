"""
C3/C4 批量评测：与 ``main.py client`` / headless 共用 ``QueryEngine`` 与编排链，仅题目来源与日志目录不同。

预设拆分（``--split``）：
- ``c3_smoke``：Q021–Q030（``questions_c3_candidates.csv``）
- ``c4_tools``：主集里 expected_path=C4 且含工具需求（Q013,Q016–Q019）
- ``main_20``：``questions.csv`` 全量 20 题
- ``ids``：``--question-ids Q001,Q002`` 显式指定
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from agentic_rag import config as app_config
from agentic_rag.deep_planning.presets import run_profile_for_preset
from agentic_rag.experiment.runner import run_knowledge_base_rag
from agentic_rag.orchestration.route_policy import (
    RouteDecision,
    apply_route_to_orchestration,
    resolve_route,
)
from agentic_rag.orchestration.types import OrchestrationConfig
from agentic_rag.runtime.engine.query_engine import QueryEngine, QueryEngineConfig
from agentic_rag.runtime.types import RuntimeEvent
from agentic_rag.telemetry.audit_log import audit_log, new_audit_session_id, set_audit_session_id
from agentic_rag.telemetry.client_hooks import build_client_audit_hooks, log_turn_result
from agentic_rag.telemetry.streaming_hooks import (
    format_runtime_event_line,
    hooks_with_runtime_events,
    merge_orchestration_hooks,
    safe_print_console,
)

SplitName = Literal["c3_smoke", "c4_tools", "main_20", "ids", "bank"]

C3_SMOKE_IDS: tuple[str, ...] = tuple(f"Q{i:03d}" for i in range(21, 31))
C4_TOOL_IDS: tuple[str, ...] = ("Q013", "Q016", "Q017", "Q018", "Q019")


@dataclass
class C34BatchTask:
    question_id: str
    question: str
    task_type: str = ""
    difficulty: str = ""
    expected_path: str = ""
    required_tool: str = ""
    note: str = ""


@dataclass
class C34BatchTaskResult:
    question_id: str
    question: str
    ok: bool
    answer: str
    stop_reason: str
    latency_ms: int
    tier: str
    session_id: str = ""
    run_index: int = 1
    events: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""


@dataclass
class C34BatchReport:
    schema_version: str = "topic4.c34_batch.v1"
    tier: str = "c3"
    split: str = ""
    planning_rewrite_enabled: bool = False
    result_csv: str = ""
    run_environment: dict[str, Any] = field(default_factory=dict)
    tasks: list[C34BatchTaskResult] = field(default_factory=list)


def _project_root() -> Path:
    return app_config.PROJECT_ROOT.resolve()


def _read_questions_csv(path: Path) -> list[C34BatchTask]:
    rows: list[C34BatchTask] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            qid = (row.get("question_id") or "").strip()
            qtext = (row.get("question") or "").strip()
            if not qid or not qtext:
                continue
            rows.append(
                C34BatchTask(
                    question_id=qid,
                    question=qtext,
                    task_type=(row.get("task_type") or "").strip(),
                    difficulty=(row.get("difficulty") or "").strip(),
                    expected_path=(row.get("expected_path") or "").strip(),
                    required_tool=(row.get("required_tool") or "").strip(),
                    note=(row.get("note") or "").strip(),
                )
            )
    return rows


def resolve_batch_tasks(
    *,
    split: SplitName,
    question_ids: list[str] | None = None,
    questions_csv: Path | None = None,
    limit: int | None = None,
) -> list[C34BatchTask]:
    root = _project_root()
    testset = root / "data" / "testset"

    if split == "c3_smoke":
        path = testset / "questions_c3_candidates.csv"
        tasks = _read_questions_csv(path)
    elif split == "c4_tools":
        tasks = [t for t in _read_questions_csv(testset / "questions.csv") if t.question_id in C4_TOOL_IDS]
    elif split == "main_20":
        path = questions_csv or (testset / "questions.csv")
        tasks = _read_questions_csv(path)
    elif split == "bank":
        if questions_csv is None or not questions_csv.is_file():
            raise ValueError("split=bank 必须通过 --questions-csv 指定题库 CSV")
        tasks = _read_questions_csv(questions_csv)
        if question_ids:
            ids = {x.strip() for x in question_ids if x.strip()}
            tasks = [t for t in tasks if t.question_id in ids]
    elif split == "ids":
        ids = {x.strip() for x in (question_ids or []) if x.strip()}
        if not ids:
            raise ValueError("split=ids 需要 --question-ids")
        merged: list[C34BatchTask] = []
        for fname in ("questions.csv", "questions_c3_candidates.csv"):
            p = testset / fname
            if p.is_file():
                merged.extend(t for t in _read_questions_csv(p) if t.question_id in ids)
        seen: set[str] = set()
        tasks = []
        for t in merged:
            if t.question_id in seen:
                continue
            seen.add(t.question_id)
            tasks.append(t)
        tasks.sort(key=lambda x: x.question_id)
    else:
        raise ValueError(f"未知 split: {split}")

    if limit is not None and limit > 0:
        tasks = tasks[:limit]
    return tasks


def _orchestration_for_tier(
    tier: str,
    *,
    enable_sandbox: bool,
    enable_planning_rewrite: bool,
    max_orchestration_rounds: int | None,
    max_execute_retries_per_round: int | None,
    use_rag_subagent_tools: bool | None = None,
    max_rag_tool_calls_per_round: int | None = None,
    enable_adaptive_routing: bool = True,
) -> OrchestrationConfig:
    enable_c4 = tier == "c4"
    config = OrchestrationConfig(
        enable_c4_tools=enable_c4,
        enable_sandbox_tools=enable_c4 and enable_sandbox,
        enable_planning_query_rewrite=enable_planning_rewrite,
        enable_adaptive_routing=enable_adaptive_routing,
    )
    if use_rag_subagent_tools is not None:
        config.use_rag_subagent_tools = bool(use_rag_subagent_tools)
    if max_orchestration_rounds is not None:
        config.max_orchestration_rounds = max(1, int(max_orchestration_rounds))
    if max_execute_retries_per_round is not None:
        config.max_execute_retries_per_round = max(1, int(max_execute_retries_per_round))
    if max_rag_tool_calls_per_round is not None:
        config.max_rag_tool_calls_per_round = max(0, int(max_rag_tool_calls_per_round))
    return config


def _default_log_dir(tier: str) -> Path:
    name = "c4_tool_augmented" if tier == "c4" else "c3_agentic_retrieval"
    return _project_root() / "runs" / "logs" / f"{name}_batch"


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


C34_RESULT_FIELDS = [
    "question_id",
    "question",
    "task_type",
    "difficulty",
    "ok",
    "error",
    "stop_reason",
    "latency_ms",
    "planning_rewrite_enabled",
    "plan_generated",
    "needs_retrieval_tools",
    "suggested_pipelines",
    "rag_query_count",
    "pipeline_mentions",
    "retrieved_doc_ids",
    "retrieved_chunk_ids",
    "final_citation_chunk_ids",
    "gold_doc_count",
    "gold_doc_covered",
    "gold_doc_coverage",
    "gold_chunk_count",
    "gold_chunk_covered",
    "gold_chunk_coverage",
    "answer",
    "citations",
    "log_path",
    "execution_route",
    "route_reason",
    "rag_pipeline_preset",
]


def _read_csv_dicts(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _reference_path_for_split(split: SplitName) -> Path:
    testset = _project_root() / "data" / "testset"
    if split == "c3_smoke":
        return testset / "references_c3_candidates.csv"
    return testset / "references.csv"


def _read_references(split: SplitName) -> dict[str, dict[str, str]]:
    if split == "ids":
        refs: dict[str, dict[str, str]] = {}
        testset = _project_root() / "data" / "testset"
        for name in ("references.csv", "references_c3_candidates.csv"):
            for row in _read_csv_dicts(testset / name):
                qid = (row.get("question_id") or "").strip()
                if qid:
                    refs[qid] = row
        return refs
    return {
        (row.get("question_id") or "").strip(): row
        for row in _read_csv_dicts(_reference_path_for_split(split))
        if (row.get("question_id") or "").strip()
    }


def _result_csv_path(tier: str, split: str) -> Path:
    if tier == "c3" and split == "c3_smoke":
        return _project_root() / "runs" / "results" / "c3_formal_results.csv"
    return _project_root() / "runs" / "results" / f"{tier}_{split}_results.csv"


def _write_result_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=C34_RESULT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in C34_RESULT_FIELDS})


def _sha256_file(path: Path) -> str:
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_commit() -> str:
    try:
        cp = subprocess.run(
            ["git", "log", "-1", "--oneline"],
            cwd=_project_root(),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError:
        return ""
    return (cp.stdout or "").strip()


def _git_status_short() -> str:
    try:
        cp = subprocess.run(
            ["git", "status", "--short"],
            cwd=_project_root(),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError:
        return ""
    return (cp.stdout or "").strip()


def _run_environment() -> dict[str, Any]:
    processed = _project_root() / "data" / "processed"
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "git_status_short": _git_status_short(),
        "python_version": sys.version.split()[0],
        "documents_csv_sha256": _sha256_file(processed / "documents.csv"),
        "chunks_jsonl_sha256": _sha256_file(processed / "chunks.jsonl"),
    }


def _json_cell(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _split_ids(value: str) -> list[str]:
    raw = (value or "").strip()
    if not raw:
        return []
    return [x.strip() for x in re.split(r"[,;，；]", raw) if x.strip()]


def _unique(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _chunk_ids_in_text(text: str) -> list[str]:
    return _unique(re.findall(r"doc_\d+::chunk_\d+", text or ""))


def _chunk_ids_from_citations(citations: list[Any]) -> list[str]:
    ids: list[str] = []
    for item in citations:
        if isinstance(item, dict):
            cid = str(item.get("chunk_id") or "").strip()
            if cid:
                ids.append(cid)
        elif isinstance(item, str):
            ids.extend(_chunk_ids_in_text(item))
    return _unique(ids)


def _extract_last_assistant_from_state(raw_state: dict[str, Any] | None) -> str:
    if not raw_state:
        return ""
    last_state = raw_state.get("last_state")
    if not isinstance(last_state, dict):
        return ""
    try:
        from agentic_rag.orchestration.evidence_extract import extract_last_assistant_text

        return extract_last_assistant_text(last_state.get("messages")).strip()
    except Exception:
        return ""


def _load_trace_rows(session_id: str) -> list[dict[str, Any]]:
    try:
        from agentic_rag.telemetry.session_trace import load_session_trace

        return load_session_trace(session_id)
    except Exception:
        return []


def _trace_path(session_id: str) -> str:
    try:
        from agentic_rag.telemetry.session_trace import session_trace_path

        return str(session_trace_path(session_id))
    except Exception:
        return ""


def _summarize_trace(rows: list[dict[str, Any]]) -> dict[str, Any]:
    plan_payload: dict[str, Any] = {}
    rag_events: list[dict[str, Any]] = []
    tool_counts: dict[str, int] = {}
    for row in rows:
        event = str(row.get("event") or "")
        payload = row.get("payload")
        if event == "layer1_plan" and isinstance(payload, dict) and not plan_payload:
            plan_payload = payload
        if event == "rag_query_result" and isinstance(payload, dict):
            rag_events.append(payload)
        if event == "tool_invoke_start" and isinstance(payload, dict):
            tname = str(payload.get("tool") or payload.get("name") or "").strip()
            if tname:
                tool_counts[tname] = tool_counts.get(tname, 0) + 1

    pipelines: list[str] = []
    doc_ids: list[str] = []
    chunk_ids: list[str] = []
    citations: list[Any] = []
    for payload in rag_events:
        pipeline = str(payload.get("pipeline") or "").strip()
        if pipeline:
            pipelines.append(pipeline)
        for chunk in payload.get("retrieved_chunks") or []:
            if not isinstance(chunk, dict):
                continue
            doc_id = str(chunk.get("doc_id") or "").strip()
            chunk_id = str(chunk.get("chunk_id") or "").strip()
            if doc_id:
                doc_ids.append(doc_id)
            if chunk_id:
                chunk_ids.append(chunk_id)
        raw_citations = payload.get("citations")
        if isinstance(raw_citations, list):
            citations.extend(raw_citations)

    return {
        "plan_generated": bool(plan_payload),
        "needs_retrieval_tools": plan_payload.get("needs_retrieval_tools", ""),
        "suggested_pipelines": _unique([str(x) for x in plan_payload.get("suggested_pipelines") or []]),
        "rag_query_count": len(rag_events),
        "tool_invoke_counts": tool_counts,
        "pipeline_mentions": _unique(pipelines),
        "retrieved_doc_ids": _unique(doc_ids),
        "retrieved_chunk_ids": _unique(chunk_ids),
        "citations": citations,
    }


def _formal_result_row(
    *,
    task: C34BatchTask,
    row: C34BatchTaskResult,
    reference: dict[str, str] | None,
    planning_rewrite_enabled: bool,
    answer: str,
    route: RouteDecision | None = None,
) -> dict[str, Any]:
    trace = _summarize_trace(_load_trace_rows(row.session_id))
    gold_doc_ids = _split_ids((reference or {}).get("evidence_doc_id", ""))
    gold_chunk_ids = _split_ids((reference or {}).get("evidence_chunk_id", ""))
    retrieved_doc_ids = trace["retrieved_doc_ids"]
    retrieved_chunk_ids = trace["retrieved_chunk_ids"]
    final_citation_chunk_ids = _chunk_ids_in_text(answer)
    if not final_citation_chunk_ids:
        final_citation_chunk_ids = _chunk_ids_from_citations(trace["citations"])

    retrieved_doc_set = set(retrieved_doc_ids)
    retrieved_chunk_set = set(retrieved_chunk_ids)
    gold_doc_covered = sum(1 for doc_id in gold_doc_ids if doc_id in retrieved_doc_set)
    gold_chunk_covered = sum(1 for chunk_id in gold_chunk_ids if chunk_id in retrieved_chunk_set)
    gold_doc_count = len(gold_doc_ids)
    gold_chunk_count = len(gold_chunk_ids)

    return {
        "question_id": task.question_id,
        "question": task.question,
        "task_type": task.task_type,
        "difficulty": task.difficulty,
        "ok": row.ok,
        "error": row.error,
        "stop_reason": row.stop_reason,
        "latency_ms": row.latency_ms,
        "planning_rewrite_enabled": planning_rewrite_enabled,
        "plan_generated": trace["plan_generated"],
        "needs_retrieval_tools": trace["needs_retrieval_tools"],
        "suggested_pipelines": _json_cell(trace["suggested_pipelines"]),
        "rag_query_count": trace["rag_query_count"],
        "pipeline_mentions": _json_cell(trace["pipeline_mentions"]),
        "retrieved_doc_ids": _json_cell(retrieved_doc_ids),
        "retrieved_chunk_ids": _json_cell(retrieved_chunk_ids),
        "final_citation_chunk_ids": _json_cell(final_citation_chunk_ids),
        "gold_doc_count": gold_doc_count,
        "gold_doc_covered": gold_doc_covered,
        "gold_doc_coverage": round(gold_doc_covered / gold_doc_count, 4) if gold_doc_count else "",
        "gold_chunk_count": gold_chunk_count,
        "gold_chunk_covered": gold_chunk_covered,
        "gold_chunk_coverage": round(gold_chunk_covered / gold_chunk_count, 4) if gold_chunk_count else "",
        "answer": answer,
        "citations": _json_cell(final_citation_chunk_ids or trace["citations"]),
        "log_path": _trace_path(row.session_id),
        "execution_route": route.mode if route else "c3_orchestrated",
        "route_reason": route.reason if route else "",
        "rag_pipeline_preset": route.rag_preset if route else "",
    }


def _chunks_from_kb_raw(raw: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    doc_ids: list[str] = []
    chunk_ids: list[str] = []
    for ch in raw.get("retrieved_chunks") or []:
        if not isinstance(ch, dict):
            continue
        did = str(ch.get("doc_id") or "").strip()
        cid = str(ch.get("chunk_id") or "").strip()
        if did and did not in doc_ids:
            doc_ids.append(did)
        if cid:
            chunk_ids.append(cid)
    citations = _chunk_ids_from_citations(raw.get("citations") or [])
    if not citations:
        citations = chunk_ids[:]
    return doc_ids, chunk_ids, citations


def _run_c2_kb_task(
    task: C34BatchTask,
    route: RouteDecision,
    *,
    tier: str,
    session_id: str,
    run_index: int,
) -> tuple[C34BatchTaskResult, dict[str, Any]]:
    """单次全库 RAG（C0/C1/C2 预设），跳过三层编排。"""
    profile = run_profile_for_preset(route.rag_preset)
    profile.question_id = task.question_id
    profile.save_jsonl_log = False
    t0 = time.perf_counter()
    raw = run_knowledge_base_rag(task.question, profile)
    latency = int((time.perf_counter() - t0) * 1000)
    err = str(raw.get("error") or "").strip()
    answer = str(raw.get("answer") or "").strip()
    if err and not answer:
        answer = f"（检索失败：{err}）"
    ok = bool(answer) and not err
    doc_ids, chunk_ids, _ = _chunks_from_kb_raw(raw)
    audit_log(
        "c2_kb_batch_answer",
        session_id=session_id,
        payload={
            "question_id": task.question_id,
            "pipeline": route.rag_preset,
            "route_reason": route.reason,
            "latency_ms": latency,
            "error": err or None,
            "retrieved_doc_ids": doc_ids,
            "retrieved_chunk_ids": chunk_ids,
        },
    )
    row = C34BatchTaskResult(
        question_id=task.question_id,
        question=task.question,
        ok=ok,
        answer=answer,
        stop_reason="complete" if ok else "error",
        latency_ms=latency,
        tier=tier,
        session_id=session_id,
        run_index=run_index,
        events=[
            {
                "kind": "route",
                "message": f"c2_kb preset={route.rag_preset}",
                "payload": {"reason": route.reason},
            }
        ],
        error=err,
    )
    return row, raw


def _formal_row_for_c2_kb(
    *,
    task: C34BatchTask,
    row: C34BatchTaskResult,
    route: RouteDecision,
    reference: dict[str, str] | None,
    planning_rewrite_enabled: bool,
    kb_raw: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """C2 轻路径结果行（使用单次 RAG 返回的 chunk 列表）。"""
    if kb_raw:
        doc_ids, chunk_ids, citations = _chunks_from_kb_raw(kb_raw)
    else:
        chunk_ids = _chunk_ids_in_text(row.answer)
        doc_ids = _unique([c.split("::")[0] for c in chunk_ids if "::" in c])
        citations = chunk_ids
    gold_doc_ids = _split_ids((reference or {}).get("evidence_doc_id") or "")
    gold_chunk_ids = _split_ids((reference or {}).get("evidence_chunk_id") or "")
    gold_doc_covered = sum(1 for d in gold_doc_ids if d in doc_ids)
    gold_chunk_covered = sum(1 for c in gold_chunk_ids if c in chunk_ids)
    return {
        "question_id": task.question_id,
        "question": task.question,
        "task_type": task.task_type,
        "difficulty": task.difficulty,
        "ok": row.ok,
        "error": row.error,
        "stop_reason": row.stop_reason,
        "latency_ms": row.latency_ms,
        "planning_rewrite_enabled": planning_rewrite_enabled,
        "plan_generated": False,
        "needs_retrieval_tools": True,
        "suggested_pipelines": _json_cell([route.rag_preset]),
        "rag_query_count": 1 if row.ok else 0,
        "pipeline_mentions": _json_cell([route.rag_preset]),
        "retrieved_doc_ids": _json_cell(doc_ids),
        "retrieved_chunk_ids": _json_cell(chunk_ids),
        "final_citation_chunk_ids": _json_cell(citations),
        "gold_doc_count": len(gold_doc_ids),
        "gold_doc_covered": gold_doc_covered,
        "gold_doc_coverage": round(gold_doc_covered / len(gold_doc_ids), 4)
        if gold_doc_ids
        else "",
        "gold_chunk_count": len(gold_chunk_ids),
        "gold_chunk_covered": gold_chunk_covered,
        "gold_chunk_coverage": round(gold_chunk_covered / len(gold_chunk_ids), 4)
        if gold_chunk_ids
        else "",
        "answer": row.answer,
        "citations": _json_cell(citations),
        "log_path": _trace_path(row.session_id),
        "execution_route": route.mode,
        "route_reason": route.reason,
        "rag_pipeline_preset": route.rag_preset,
    }


def run_c34_batch(
    *,
    tier: str = "c3",
    split: SplitName = "c3_smoke",
    question_ids: list[str] | None = None,
    questions_csv: Path | None = None,
    limit: int | None = None,
    repeat: int = 1,
    enable_sandbox: bool = False,
    enable_planning_rewrite: bool = False,
    max_orchestration_rounds: int | None = None,
    max_execute_retries_per_round: int | None = None,
    use_rag_subagent_tools: bool | None = None,
    max_rag_tool_calls_per_round: int | None = None,
    enable_adaptive_routing: bool = True,
    log_dir: Path | None = None,
    continue_on_error: bool = True,
    stream_events_to_stdout: bool = False,
) -> C34BatchReport:
    try:
        import deepagents  # noqa: F401
    except ImportError as e:
        raise SystemExit(
            "C3/C4 批量需要 Agent 依赖：uv sync --group agent\n" f"{e}"
        ) from e

    tasks = resolve_batch_tasks(
        split=split,
        question_ids=question_ids,
        questions_csv=questions_csv,
        limit=limit,
    )
    if not tasks:
        raise SystemExit(f"未解析到题目（split={split}）")

    references = _read_references(split)
    orch_base = _orchestration_for_tier(
        tier,
        enable_sandbox=enable_sandbox,
        enable_planning_rewrite=enable_planning_rewrite,
        max_orchestration_rounds=max_orchestration_rounds,
        max_execute_retries_per_round=max_execute_retries_per_round,
        use_rag_subagent_tools=use_rag_subagent_tools,
        max_rag_tool_calls_per_round=max_rag_tool_calls_per_round,
        enable_adaptive_routing=enable_adaptive_routing,
    )
    repeat_n = max(1, int(repeat))
    out_dir = log_dir or _default_log_dir(tier)
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "run_logs.jsonl"
    report_path = out_dir / "batch_report.json"
    result_csv_path = _result_csv_path(tier, split)

    batch_session = new_audit_session_id()
    report = C34BatchReport(
        tier=tier,
        split=split,
        planning_rewrite_enabled=enable_planning_rewrite,
        result_csv=str(result_csv_path),
        run_environment=_run_environment(),
    )
    formal_rows: list[dict[str, Any]] = []

    audit_log(
        "c34_batch_start",
        session_id=batch_session,
        payload={
            "tier": tier,
            "split": split,
            "task_count": len(tasks),
            "log_dir": str(out_dir),
            "result_csv": str(result_csv_path),
            "planning_rewrite_enabled": enable_planning_rewrite,
            "max_orchestration_rounds": orch.max_orchestration_rounds,
            "max_execute_retries_per_round": orch.max_execute_retries_per_round,
            "use_rag_subagent_tools": orch.use_rag_subagent_tools,
            "max_rag_tool_calls_per_round": orch_base.max_rag_tool_calls_per_round,
            "enable_adaptive_routing": enable_adaptive_routing,
            "repeat": repeat_n,
        },
    )

    expanded: list[tuple[C34BatchTask, int]] = []
    for task in tasks:
        for run_idx in range(1, repeat_n + 1):
            expanded.append((task, run_idx))

    for task, run_idx in expanded:
        sid = new_audit_session_id()
        set_audit_session_id(sid)
        events_dump: list[dict[str, Any]] = []
        t0 = time.perf_counter()

        def on_event(ev: RuntimeEvent) -> None:
            row = {
                "kind": ev.kind,
                "message": ev.message[:2000],
                "payload": ev.payload,
            }
            events_dump.append(row)
            if stream_events_to_stdout:
                tag = task.question_id
                if repeat_n > 1:
                    tag = f"{tag}#{run_idx}"
                safe_print_console(f"  [{tag}] {format_runtime_event_line(ev)}")

        route = resolve_route(
            task_type=task.task_type,
            difficulty=task.difficulty,
            expected_path=task.expected_path,
            required_tool=task.required_tool,
            tier=tier,
            enable_adaptive_routing=enable_adaptive_routing,
        )
        if stream_events_to_stdout:
            safe_print_console(
                f"  [{task.question_id}] route={route.mode} "
                f"preset={route.rag_preset} ({route.reason})"
            )

        try:
            kb_raw: dict[str, Any] = {}
            if route.mode == "c2_kb":
                row, kb_raw = _run_c2_kb_task(
                    task,
                    route,
                    tier=tier,
                    session_id=sid,
                    run_index=run_idx,
                )
                events_dump.extend(row.events)
            else:
                orch = OrchestrationConfig(
                    enable_c4_tools=orch_base.enable_c4_tools,
                    enable_sandbox_tools=orch_base.enable_sandbox_tools,
                    enable_planning_query_rewrite=orch_base.enable_planning_query_rewrite,
                    enable_kb_inventory_hints=orch_base.enable_kb_inventory_hints,
                    use_rag_subagent_tools=orch_base.use_rag_subagent_tools,
                    enable_adaptive_routing=orch_base.enable_adaptive_routing,
                    max_orchestration_rounds=orch_base.max_orchestration_rounds,
                    max_execute_retries_per_round=orch_base.max_execute_retries_per_round,
                    max_rag_tool_calls_per_round=orch_base.max_rag_tool_calls_per_round,
                    prefer_complete_when_grounded=orch_base.prefer_complete_when_grounded,
                )
                apply_route_to_orchestration(orch, route, tier=tier)
                if max_orchestration_rounds is not None:
                    orch.max_orchestration_rounds = max(1, int(max_orchestration_rounds))
                if max_execute_retries_per_round is not None:
                    orch.max_execute_retries_per_round = max(
                        1, int(max_execute_retries_per_round)
                    )
                if max_rag_tool_calls_per_round is not None:
                    orch.max_rag_tool_calls_per_round = max(
                        0, int(max_rag_tool_calls_per_round)
                    )

                audit_hooks = build_client_audit_hooks(tier=tier, session_id=sid)
                hooks = hooks_with_runtime_events(
                    merge_orchestration_hooks(audit_hooks),
                    on_event,
                    tier=tier,
                )
                engine = QueryEngine(
                    config=QueryEngineConfig(
                        orchestration=orch,
                        hooks=hooks,
                        temperature=0.35,
                    ),
                )
                result = engine.submit_message(task.question, on_event=on_event)
                latency = int((time.perf_counter() - t0) * 1000)
                answer = (
                    _extract_last_assistant_from_state(result.raw_state)
                    or result.assistant_text
                    or result.transcript
                    or ""
                )
                row = C34BatchTaskResult(
                    question_id=task.question_id,
                    question=task.question,
                    ok=result.stop_reason not in ("error", "aborted"),
                    answer=answer,
                    stop_reason=result.stop_reason,
                    latency_ms=latency,
                    tier=tier,
                    session_id=sid,
                    run_index=run_idx,
                    events=events_dump,
                )
                log_turn_result(
                    user_text=task.question,
                    stop_reason=result.stop_reason,
                    latency_ms=latency,
                    transcript_len=len(row.answer),
                    assistant_text=row.answer,
                    tier=tier,
                    session_id=sid,
                )
        except Exception as exc:
            latency = int((time.perf_counter() - t0) * 1000)
            row = C34BatchTaskResult(
                question_id=task.question_id,
                question=task.question,
                ok=False,
                answer="",
                stop_reason="error",
                latency_ms=latency,
                tier=tier,
                session_id=sid,
                run_index=run_idx,
                events=events_dump,
                error=str(exc),
            )
            if not continue_on_error:
                report.tasks.append(row)
                _append_jsonl(jsonl_path, {**asdict(row), "task_meta": asdict(task)})
                break

        report.tasks.append(row)
        log_row = {
            **asdict(row),
            "task_type": task.task_type,
            "difficulty": task.difficulty,
            "expected_path": task.expected_path,
            "required_tool": task.required_tool,
            "note": task.note,
            "planning_rewrite_enabled": enable_planning_rewrite,
            "execution_route": route.mode,
            "route_reason": route.reason,
            "rag_pipeline_preset": route.rag_preset,
            "run_index": run_idx,
        }
        if route.mode != "c2_kb":
            log_row["max_orchestration_rounds"] = orch.max_orchestration_rounds
            log_row["max_execute_retries_per_round"] = orch.max_execute_retries_per_round
            log_row["use_rag_subagent_tools"] = orch.use_rag_subagent_tools
            log_row["max_rag_tool_calls_per_round"] = orch.max_rag_tool_calls_per_round
            log_row["max_total_rag_calls"] = orch.max_total_rag_calls
        _append_jsonl(jsonl_path, log_row)
        if route.mode == "c2_kb":
            formal_rows.append(
                _formal_row_for_c2_kb(
                    task=task,
                    row=row,
                    route=route,
                    reference=references.get(task.question_id),
                    planning_rewrite_enabled=enable_planning_rewrite,
                    kb_raw=kb_raw,
                )
            )
        else:
            formal_rows.append(
                _formal_result_row(
                    task=task,
                    row=row,
                    reference=references.get(task.question_id),
                    planning_rewrite_enabled=enable_planning_rewrite,
                    answer=row.answer,
                    route=route,
                )
            )
        _write_result_csv(result_csv_path, formal_rows)
        run_tag = f" run={run_idx}" if repeat_n > 1 else ""
        safe_print_console(
            f"[{tier}] {task.question_id}{run_tag} "
            f"{'OK' if row.ok else 'FAIL'} "
            f"{row.latency_ms}ms "
            f"session={sid}"
        )

    report_path.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    audit_log(
        "c34_batch_complete",
        session_id=batch_session,
        payload={
            "ok_count": sum(1 for t in report.tasks if t.ok),
            "total": len(report.tasks),
            "report": str(report_path),
            "jsonl": str(jsonl_path),
            "result_csv": str(result_csv_path),
            "planning_rewrite_enabled": enable_planning_rewrite,
            "max_orchestration_rounds": orch_base.max_orchestration_rounds,
            "max_execute_retries_per_round": orch_base.max_execute_retries_per_round,
            "enable_adaptive_routing": enable_adaptive_routing,
        },
    )
    return report
