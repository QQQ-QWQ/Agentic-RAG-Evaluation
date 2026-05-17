"""CLI：``main.py agent`` —— 委托 ``orchestration.run_cli_agent_session``。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _require_agent_group() -> None:
    try:
        import deepagents  # noqa: F401
        import langchain_openai  # noqa: F401
    except ImportError as e:
        raise SystemExit(
            "未安装 Agent 依赖组。请在项目根执行：\n"
            "  uv sync --group agent\n"
            f"原始错误：{e}"
        ) from None


def _resolve_cli_doc(cli_value: str | None) -> Path | None:
    if not cli_value or not str(cli_value).strip():
        return None
    p = Path(str(cli_value).strip().strip('"')).expanduser().resolve()
    if not p.is_file():
        sys.exit(f"文档不存在：{p}")
    return p


def cmd_agent(args: argparse.Namespace) -> None:
    _require_agent_group()

    from agentic_rag.orchestration.loop import run_cli_agent_session
    from agentic_rag.orchestration.types import OrchestrationConfig

    once_text = getattr(args, "once", None)
    if getattr(args, "stdin", False):
        once_text = sys.stdin.read()
    elif getattr(args, "once_file", None):
        fp = Path(str(getattr(args, "once_file")).strip().strip('"')).expanduser().resolve()
        if not fp.is_file():
            sys.exit(f"文件不存在：{fp}")
        once_text = fp.read_text(encoding="utf-8")

    once_mode = bool(once_text and str(once_text).strip())
    max_rounds = int(getattr(args, "max_rounds", 4))
    max_retries = int(getattr(args, "max_execute_retries", 2))
    # 单次注入（--once / --once-file / --stdin）默认只跑一轮外层编排、第二层不因研判重复整轮，
    # 避免大批量 CSV + continue_execute 造成双倍耗时与终端「卡死」感。需要旧行为请加 --orchestrate-repeat。
    if once_mode and not getattr(args, "orchestrate_repeat", False):
        max_rounds = 1
        max_retries = 1
        print(
            "[编排] 单次注入：已限制外层编排 1 轮、第二层不因研判重复执行；"
            "需要研判驱动的重复时请使用 --orchestrate-repeat（并可配合 --max-rounds / --max-execute-retries）。\n"
        )

    enable_c4 = bool(getattr(args, "c4", False))
    if getattr(args, "c3", False):
        enable_c4 = False
    cfg = OrchestrationConfig(
        enable_judge=not getattr(args, "no_judge", False),
        max_orchestration_rounds=max_rounds,
        max_execute_retries_per_round=max_retries,
        orchestrate_follow_ups=bool(getattr(args, "full_each_turn", False)),
        enable_kb_grounding_judge=not getattr(args, "no_kb_grounding", False),
        enable_sandbox_tools=enable_c4 and not getattr(args, "no_sandbox", False),
        enable_planning_query_rewrite=bool(getattr(args, "planning_rewrite", False)),
        enable_kb_inventory_hints=not getattr(args, "no_kb_inventory_hints", False),
        enable_c4_tools=enable_c4,
    )
    if enable_c4:
        print("[agent] 档位：C4 Tool-Augmented（含外部工具）\n")
    else:
        print("[agent] 档位：C3 Agentic Retrieval（仅检索工具，默认）\n")
    pf = getattr(args, "planning_rewrite_prompt", None)
    if pf:
        cfg.planning_rewrite_prompt_file = Path(str(pf).strip().strip('"')).expanduser().resolve()

    run_cli_agent_session(
        cli_doc=_resolve_cli_doc(getattr(args, "doc_path", None)),
        skip_layer1=bool(getattr(args, "skip_layer1", False)),
        once_text=once_text,
        temperature=float(getattr(args, "temperature", 0.35)),
        json_debug=bool(getattr(args, "json", False)),
        config=cfg,
        multiline_interactive=not bool(getattr(args, "single_line", False)),
    )


def build_agent_parser(*, add_help: bool = True) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        add_help=add_help,
        description=(
            "多层级编排：第一层规划 → 第二层 Deep Agent + Topic4 RAG → 第三层研判。"
            "需 uv sync --group agent。"
        ),
    )
    p.add_argument(
        "doc_path",
        nargs="?",
        default=None,
        metavar="PATH",
        help="可选：绑定单份本地文档（单文件 Chroma 索引）；省略则默认全库知识库",
    )
    p.add_argument(
        "--once",
        "-o",
        metavar="TEXT",
        default=None,
        help="非交互：对一段自然语言跑完整编排（规划→执行→研判循环）",
    )
    p.add_argument(
        "--once-file",
        metavar="PATH",
        default=None,
        help="从 UTF-8 文件读取整段任务文本（等同 --once，适合长问题、多轮提问列表）",
    )
    p.add_argument(
        "--stdin",
        action="store_true",
        help="从标准输入读取整段任务文本（优先级高于 --once / --once-file）",
    )
    p.add_argument(
        "--single-line",
        action="store_true",
        help="交互时每轮只读一行（旧行为）；默认已启用多行模式，便于粘贴 CSV/长文本（结束后单独一行 END）",
    )
    p.add_argument("--temperature", type=float, default=0.35, help="第二层采样温度")
    p.add_argument(
        "--skip-layer1",
        action="store_true",
        help="调试：跳过第一层；可不绑文档（默认全库）或配合 doc_path 绑单文件",
    )
    p.add_argument(
        "--no-judge",
        action="store_true",
        help="关闭第三层研判（仅规划+执行，便于调试）",
    )
    p.add_argument(
        "--max-rounds",
        type=int,
        default=4,
        metavar="N",
        help="外层编排最大轮次（含重规划），默认 4；与 --once/--once-file 联用时默认会被收紧为 1，除非再加 --orchestrate-repeat",
    )
    p.add_argument(
        "--max-execute-retries",
        type=int,
        default=2,
        metavar="N",
        help="同一轮规划下第二层最多执行次数（研判 continue_execute 时），默认 2；与单次注入联用时默认 1，除非 --orchestrate-repeat",
    )
    p.add_argument(
        "--orchestrate-repeat",
        action="store_true",
        help=(
            "允许单次任务（--once/--once-file/--stdin）按上述 --max-* 重复外层编排或第二层执行；"
            "默认关闭以避免研判触发整轮重复调用。"
        ),
    )
    p.add_argument(
        "--full-each-turn",
        action="store_true",
        help="交互后续每一轮用户输入都走完整三层（默认仅第二层）",
    )
    p.add_argument(
        "--no-kb-grounding",
        action="store_true",
        help="关闭「检索摘录 vs 答复」对齐核验（不与第三层研判合并参考）",
    )
    p.add_argument(
        "--no-sandbox",
        action="store_true",
        help="不请求挂载 sandbox_exec_python（仍需 SANDBOX_ENABLED=true 才真正注册）",
    )
    p.add_argument(
        "--planning-rewrite",
        action="store_true",
        help="第一层前先跑 C1 同源 query 改写，辅助识别检索意图（多一次 DeepSeek 调用）",
    )
    p.add_argument(
        "--planning-rewrite-prompt",
        metavar="PATH",
        default=None,
        help="改写提示词文件路径；默认 prompts/query_rewrite_prompt.md",
    )
    p.add_argument(
        "--no-kb-inventory-hints",
        action="store_true",
        help="不向第二层注入 documents.csv 登记状态备注（默认会注入，便于区分是否已入库）",
    )
    p.add_argument("--json", action="store_true", help="--once 模式下附加 messages 调试 JSON")
    p.add_argument(
        "--c4",
        action="store_true",
        help="C4 工具增强（入库 / MarkItDown / 可选沙箱）；默认 C3 仅检索",
    )
    p.add_argument(
        "--c3",
        action="store_true",
        help="显式 C3 仅检索（默认行为，与未指定 --c4 相同）",
    )
    return p


def main_standalone() -> None:
    ns = build_agent_parser(add_help=True).parse_args()
    cmd_agent(ns)


if __name__ == "__main__":
    main_standalone()
