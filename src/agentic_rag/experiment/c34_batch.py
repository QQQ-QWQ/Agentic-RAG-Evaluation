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
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from agentic_rag import config as app_config
from agentic_rag.orchestration.types import OrchestrationConfig
from agentic_rag.runtime.engine.query_engine import QueryEngine, QueryEngineConfig
from agentic_rag.runtime.types import RuntimeEvent
from agentic_rag.telemetry.audit_log import audit_log, new_audit_session_id, set_audit_session_id
from agentic_rag.telemetry.client_hooks import build_client_audit_hooks, log_turn_result
from agentic_rag.telemetry.streaming_hooks import (
    format_runtime_event_line,
    hooks_with_runtime_events,
    merge_orchestration_hooks,
)

SplitName = Literal["c3_smoke", "c4_tools", "main_20", "ids"]

C3_SMOKE_IDS: tuple[str, ...] = tuple(f"Q{i:03d}" for i in range(21, 31))
C4_TOOL_IDS: tuple[str, ...] = ("Q013", "Q016", "Q017", "Q018", "Q019")


@dataclass
class C34BatchTask:
    question_id: str
    question: str
    task_type: str = ""
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
    events: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""


@dataclass
class C34BatchReport:
    schema_version: str = "topic4.c34_batch.v1"
    tier: str = "c3"
    split: str = ""
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


def _orchestration_for_tier(tier: str, *, enable_sandbox: bool) -> OrchestrationConfig:
    enable_c4 = tier == "c4"
    return OrchestrationConfig(
        enable_c4_tools=enable_c4,
        enable_sandbox_tools=enable_c4 and enable_sandbox,
    )


def _default_log_dir(tier: str) -> Path:
    name = "c4_tool_augmented" if tier == "c4" else "c3_agentic_retrieval"
    return _project_root() / "runs" / "logs" / f"{name}_batch"


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_c34_batch(
    *,
    tier: str = "c3",
    split: SplitName = "c3_smoke",
    question_ids: list[str] | None = None,
    questions_csv: Path | None = None,
    limit: int | None = None,
    enable_sandbox: bool = False,
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

    orch = _orchestration_for_tier(tier, enable_sandbox=enable_sandbox)
    out_dir = log_dir or _default_log_dir(tier)
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "run_logs.jsonl"
    report_path = out_dir / "batch_report.json"

    batch_session = new_audit_session_id()
    report = C34BatchReport(tier=tier, split=split)

    audit_log(
        "c34_batch_start",
        session_id=batch_session,
        payload={
            "tier": tier,
            "split": split,
            "task_count": len(tasks),
            "log_dir": str(out_dir),
        },
    )

    for task in tasks:
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
                print(f"  [{task.question_id}] {format_runtime_event_line(ev)}")

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

        try:
            result = engine.submit_message(task.question, on_event=on_event)
            latency = int((time.perf_counter() - t0) * 1000)
            row = C34BatchTaskResult(
                question_id=task.question_id,
                question=task.question,
                ok=result.stop_reason not in ("error", "aborted"),
                answer=result.assistant_text or result.transcript or "",
                stop_reason=result.stop_reason,
                latency_ms=latency,
                tier=tier,
                session_id=sid,
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
            "expected_path": task.expected_path,
            "required_tool": task.required_tool,
            "note": task.note,
        }
        _append_jsonl(jsonl_path, log_row)
        print(
            f"[{tier}] {task.question_id} "
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
        },
    )
    return report
