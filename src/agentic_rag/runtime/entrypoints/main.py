"""运行时主编排：setup + 模式分流（REPL / headless）。"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from agentic_rag.runtime.setup import run_setup
from agentic_rag.runtime.tracing import TraceCollector


@dataclass
class RuntimeLaunchOptions:
    mode: str = "repl"
    tier: str = "c3"
    doc_path: Path | None = None
    enable_sandbox: bool = False
    tasks_file: Path | None = None
    output_format: str = "text"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="runtime", description="Agent Runtime（REPL / headless）")
    sub = p.add_subparsers(dest="command", required=True)

    repl = sub.add_parser("repl", help="交互模式")
    repl.add_argument("--c4", action="store_true")
    repl.add_argument("--c3", action="store_true")
    repl.add_argument("--sandbox", action="store_true")
    repl.add_argument("doc_path", nargs="?", default=None)

    headless = sub.add_parser("headless", help="无头批处理")
    headless.add_argument("--c4", action="store_true")
    headless.add_argument("--tasks", required=True, help="每行一条问题的文本文件")
    headless.add_argument(
        "--format",
        choices=("text", "json", "stream-json"),
        default="text",
    )
    headless.add_argument("--continue-on-error", action="store_true")
    return p


def run_runtime_main(
    argv: list[str] | None = None,
    *,
    startup_trace: TraceCollector | None = None,
) -> int:
    trace = startup_trace or TraceCollector()
    parser = _build_parser()
    args = parser.parse_args(argv)

    setup = run_setup()
    if not setup.ok:
        print(f"初始化失败：{setup.message}", file=sys.stderr)
        if setup.fix_hint:
            print(f"建议：{setup.fix_hint}", file=sys.stderr)
        return 2

    trace.mark("setup_ok", session_id=setup.session_id)

    enable_c4 = bool(getattr(args, "c4", False))
    if getattr(args, "c3", False):
        enable_c4 = False

    doc: Path | None = None
    raw_doc = getattr(args, "doc_path", None)
    if raw_doc and str(raw_doc).strip():
        doc = Path(str(raw_doc)).expanduser().resolve()
        if not doc.is_file():
            print(f"文档不存在：{doc}", file=sys.stderr)
            return 2

    opts = RuntimeLaunchOptions(
        mode="repl" if args.command == "repl" else "headless",
        tier="c4" if enable_c4 else "c3",
        doc_path=doc,
        enable_sandbox=bool(getattr(args, "sandbox", False)),
        tasks_file=Path(args.tasks).resolve() if args.command == "headless" else None,
        output_format=getattr(args, "format", "text"),
    )

    if opts.mode == "repl":
        from agentic_rag.runtime.interaction.repl import launch_repl

        launch_repl(opts, setup=setup)
        return 0

    from agentic_rag.runtime.headless.runner import run_headless

    return run_headless(opts, setup=setup, continue_on_error=bool(getattr(args, "continue_on_error", False)))
