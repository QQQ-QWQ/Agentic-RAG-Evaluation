#!/usr/bin/env python3
"""C3/C4 批量评测入口（与 ``main.py client`` 共用 QueryEngine，题目来自 CSV 预设拆分）。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def build_c34_batch_parser(*, add_help: bool = True) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        add_help=add_help,
        description="C3/C4 批量评测：共用生产编排链，仅题目拆分与日志目录不同",
    )
    parser.add_argument(
        "--tier",
        choices=("c3", "c4"),
        default="c3",
        help="c3=仅检索编排；c4=工具增强",
    )
    parser.add_argument(
        "--split",
        choices=("c3_smoke", "c4_tools", "main_20", "ids"),
        default="c3_smoke",
        help="题目预设：c3_smoke(Q021-030) | c4_tools | main_20 | ids",
    )
    parser.add_argument(
        "--question-ids",
        default="",
        help="split=ids 时逗号分隔，如 Q001,Q016",
    )
    parser.add_argument("--questions-csv", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--sandbox",
        action="store_true",
        help="C4 时注册 sandbox_exec_python（需 SANDBOX_ENABLED=true）",
    )
    parser.add_argument(
        "--planning-rewrite",
        action="store_true",
        help="Enable C1 query rewrite before layer-1 planning.",
    )
    parser.add_argument(
        "--max-orchestration-rounds",
        type=int,
        default=None,
        help="Override C3/C4 outer planning-execution-judge rounds.",
    )
    parser.add_argument(
        "--max-execute-retries-per-round",
        type=int,
        default=None,
        help="Override layer-2 execute retries in each orchestration round.",
    )
    parser.add_argument("--log-dir", type=Path, default=None)
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="首题失败即停止（默认继续）",
    )
    parser.add_argument(
        "--verbose-events",
        action="store_true",
        help="每题打印编排事件行",
    )
    return parser


def main_from_args(args: argparse.Namespace) -> int:
    qids = [x.strip() for x in args.question_ids.split(",") if x.strip()] or None
    split = args.split
    if split == "ids" and not qids:
        print("split=ids 时必须提供 --question-ids", file=sys.stderr)
        return 2

    from agentic_rag.experiment.c34_batch import run_c34_batch

    report = run_c34_batch(
        tier=args.tier,
        split=split,  # type: ignore[arg-type]
        question_ids=qids,
        questions_csv=args.questions_csv,
        limit=args.limit,
        enable_sandbox=args.sandbox,
        enable_planning_rewrite=args.planning_rewrite,
        max_orchestration_rounds=args.max_orchestration_rounds,
        max_execute_retries_per_round=args.max_execute_retries_per_round,
        log_dir=args.log_dir,
        continue_on_error=not args.fail_fast,
        stream_events_to_stdout=args.verbose_events,
    )
    failed = [t for t in report.tasks if not t.ok]
    print(
        f"\n完成：{len(report.tasks) - len(failed)}/{len(report.tasks)} 成功；"
        f"失败 {len(failed)}"
    )
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    return main_from_args(build_c34_batch_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
