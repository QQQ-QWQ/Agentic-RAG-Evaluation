"""无头批处理：复用 QueryEngine，结构化输出。"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from agentic_rag.orchestration.types import OrchestrationConfig
from agentic_rag.runtime.engine.query_engine import QueryEngine, QueryEngineConfig
from agentic_rag.runtime.entrypoints.main import RuntimeLaunchOptions
from agentic_rag.runtime.setup import SetupResult
from agentic_rag.runtime.state.app_state import AppState, SessionState
from agentic_rag.runtime.state.store import AppStateStore


@dataclass
class HeadlessTaskResult:
    task_id: str
    question: str
    ok: bool
    answer: str
    stop_reason: str
    latency_ms: int
    events: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""


@dataclass
class HeadlessRunReport:
    schema_version: str = "topic4.headless.v1"
    tier: str = "c3"
    tasks: list[HeadlessTaskResult] = field(default_factory=list)


def _load_tasks(path: Path) -> list[tuple[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[tuple[str, str]] = []
    for i, line in enumerate(lines, start=1):
        q = line.strip()
        if not q or q.startswith("#"):
            continue
        out.append((f"q{i:04d}", q))
    return out


def run_headless(
    opts: RuntimeLaunchOptions,
    *,
    setup: SetupResult,
    continue_on_error: bool = False,
) -> int:
    if opts.tasks_file is None or not opts.tasks_file.is_file():
        print("缺少有效 --tasks 文件", file=sys.stderr)
        return 2

    try:
        import deepagents  # noqa: F401
    except ImportError:
        print("无头模式需要 uv sync --group agent", file=sys.stderr)
        return 2

    tasks = _load_tasks(opts.tasks_file)
    if not tasks:
        print("任务文件为空", file=sys.stderr)
        return 2

    orch = OrchestrationConfig(enable_c4_tools=opts.tier == "c4")
    store = AppStateStore(
        AppState(
            mode="headless",
            tier=opts.tier,  # type: ignore[arg-type]
            session=SessionState(
                session_id=setup.session_id,
                project_root=str(setup.project_root),
                cwd=str(setup.cwd),
            ),
        )
    )
    engine = QueryEngine(
        store=store,
        config=QueryEngineConfig(orchestration=orch, cli_doc=opts.doc_path),
    )

    report = HeadlessRunReport(tier=opts.tier)
    exit_code = 0

    for task_id, question in tasks:
        t0 = time.perf_counter()
        events_dump: list[dict[str, Any]] = []
        try:

            def on_event(ev) -> None:
                row = {"kind": ev.kind, "message": ev.message[:500]}
                events_dump.append(row)
                if opts.output_format == "stream-json":
                    print(json.dumps({"task_id": task_id, "event": row}, ensure_ascii=False))

            result = engine.submit_message(question, on_event=on_event)
            latency = int((time.perf_counter() - t0) * 1000)
            row = HeadlessTaskResult(
                task_id=task_id,
                question=question,
                ok=result.stop_reason != "error",
                answer=result.assistant_text,
                stop_reason=result.stop_reason,
                latency_ms=latency,
                events=events_dump,
            )
        except Exception as exc:
            latency = int((time.perf_counter() - t0) * 1000)
            row = HeadlessTaskResult(
                task_id=task_id,
                question=question,
                ok=False,
                answer="",
                stop_reason="error",
                latency_ms=latency,
                error=str(exc),
            )
            exit_code = max(exit_code, 1)
            if not continue_on_error:
                report.tasks.append(row)
                break

        report.tasks.append(row)
        if opts.output_format == "text":
            status = "OK" if row.ok else "FAIL"
            print(f"\n=== {task_id} [{status}] {question[:80]} ===\n")
            print(row.answer or row.error)

    if opts.output_format == "json":
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))

    return exit_code
