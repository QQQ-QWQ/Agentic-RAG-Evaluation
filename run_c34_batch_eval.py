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
        choices=("c3_smoke", "c4_tools", "main_20", "ids", "bank"),
        default="c3_smoke",
        help="题目预设：c3_smoke | c4_tools | main_20 | ids | bank(需 --questions-csv)",
    )
    parser.add_argument(
        "--question-ids",
        default="",
        help="split=ids 时逗号分隔，如 Q001,Q016",
    )
    parser.add_argument("--questions-csv", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="每题重复跑 N 次（独立 session + audit trace），用于稳定性对比",
    )
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
    parser.add_argument(
        "--no-subagent-tools",
        action="store_true",
        help="禁用 rag_subagent_c0/c1/c2，回退 topic4_list + topic4_rag_query",
    )
    parser.add_argument(
        "--max-rag-calls",
        type=int,
        default=None,
        help="单轮第二层 RAG 类工具调用上限（默认 10）",
    )
    parser.add_argument(
        "--c3-conservative-opt",
        action="store_true",
        help="开启 C3 内部保守优化：重复检索抑制、引用筛选提示和 claim-level self-check",
    )
    parser.add_argument(
        "--c3-final-opt",
        action="store_true",
        help="Enable C3-final required-item coverage repair without changing C3 conservative runs.",
    )
    parser.add_argument(
        "--c3-ablate-required-items",
        action="store_true",
        help="C3 ablation: disable required-item extraction and targeted repair.",
    )
    parser.add_argument(
        "--c3-ablate-evidence-grader",
        action="store_true",
        help="C3 ablation: route C3-final through a no-evidence-grader preset.",
    )
    parser.add_argument(
        "--c3-ablate-rrf",
        action="store_true",
        help="C3 ablation: route C3-final through score fusion instead of RRF.",
    )
    parser.add_argument(
        "--c3-ablate-claim-check",
        action="store_true",
        help="C3 ablation: disable claim-level grounding and judge prompts.",
    )
    parser.add_argument(
        "--disable-tools",
        default="",
        help="C4 ablation: comma-separated logical/concrete tools to disable, e.g. file_reader,calculator,table_analyzer,code_runner,all.",
    )
    parser.add_argument(
        "--c4-ablate-tool-citation",
        action="store_true",
        help="C4 ablation: do not bind final answer claims to [tool:...] citations.",
    )
    parser.add_argument(
        "--c4-ablate-tool-priority-prompt",
        action="store_true",
        help="C4 ablation: weaken task-specific tool-priority prompt rules.",
    )
    parser.add_argument(
        "--force-rag-preset",
        default="",
        help="强制所有题走指定 C0/C1/C2 RAG preset，用于 C2 Stage2/Stage3 同题对照",
    )
    parser.add_argument(
        "--result-csv",
        type=Path,
        default=None,
        help="显式指定结果 CSV，避免不同对照实验互相覆盖",
    )
    parser.add_argument(
        "--no-adaptive-route",
        action="store_true",
        help="关闭按 expected_path/题型 的 C2 轻路径路由，全部走完整 C3/C4 编排",
    )
    return parser


def main_from_args(args: argparse.Namespace) -> int:
    qids = [x.strip() for x in args.question_ids.split(",") if x.strip()] or None
    split = args.split
    if split == "ids" and not qids:
        print("split=ids 时必须提供 --question-ids", file=sys.stderr)
        return 2
    if split == "bank" and args.questions_csv is None:
        print("split=bank 时必须提供 --questions-csv", file=sys.stderr)
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
        repeat=args.repeat,
        use_rag_subagent_tools=not args.no_subagent_tools,
        max_rag_tool_calls_per_round=args.max_rag_calls,
        enable_c3_conservative_optimization=args.c3_conservative_opt,
        enable_c3_final_optimization=args.c3_final_opt,
        c3_ablate_required_items=args.c3_ablate_required_items,
        c3_ablate_evidence_grader=args.c3_ablate_evidence_grader,
        c3_ablate_rrf=args.c3_ablate_rrf,
        c3_ablate_claim_check=args.c3_ablate_claim_check,
        c4_disabled_tools=[
            x.strip() for x in args.disable_tools.split(",") if x.strip()
        ],
        c4_ablate_tool_citation=args.c4_ablate_tool_citation,
        c4_ablate_tool_priority_prompt=args.c4_ablate_tool_priority_prompt,
        force_rag_preset=args.force_rag_preset or None,
        result_csv=args.result_csv,
        log_dir=args.log_dir,
        continue_on_error=not args.fail_fast,
        stream_events_to_stdout=args.verbose_events,
        enable_adaptive_routing=not args.no_adaptive_route,
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
