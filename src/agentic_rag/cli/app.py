"""
Topic4 统一 CLI：chat / rag / experiment / score / demo / ui。

新能力请在 ``src/agentic_rag/`` 实现函数接口，在此注册子命令；尽量不要再增加仓库根目录独立脚本。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agentic_rag import config
from agentic_rag.cli import demos
from agentic_rag.experiment import (
    RunProfile,
    load_profile_yaml,
    merge_profile_dict,
    run_document_rag,
)
from agentic_rag.cli.hub import run_integrated_hub
from agentic_rag.deep_planning.agent_cli import build_agent_parser
from agentic_rag.experiment.active_session import (
    apply_active_session,
    default_session_path,
    interactive_configure_session,
    save_session_from_profile,
)
from agentic_rag.llm import create_deepseek_client


def _ensure_deepseek_key() -> None:
    if not config.DEEPSEEK_API_KEY:
        sys.exit("请在 .env 中填写 DEEPSEEK_API_KEY")


def cmd_chat(args: argparse.Namespace) -> None:
    _ensure_deepseek_key()
    client = create_deepseek_client()
    text = args.prompt
    if text is None:
        text = input("输入一句话: ")
    r = client.chat.completions.create(
        model=config.DEEPSEEK_CHAT_MODEL or "deepseek-chat",
        messages=[{"role": "user", "content": text}],
    )
    print(r.choices[0].message.content or "")


def cmd_rag(args: argparse.Namespace) -> None:
    # 合并顺序：默认 RunProfile → configs/active_session.yaml → -c YAML → CLI
    profile = RunProfile()
    apply_active_session(profile)
    if args.config:
        overlay = load_profile_yaml(Path(args.config))
        merge_profile_dict(profile, overlay.to_dict())

    if args.no_chroma:
        profile.use_chroma_cache = False
    if args.no_hybrid:
        profile.use_hybrid_retrieval = False
    if args.no_rewrite:
        profile.use_query_rewrite = False
    if args.log:
        profile.save_jsonl_log = True
    if args.question_id:
        profile.question_id = args.question_id
    if args.no_rerank:
        profile.use_rerank = False
    elif args.rerank:
        profile.use_rerank = True

    overrides: dict = {}
    if args.dense_weight is not None:
        overrides["dense_weight"] = args.dense_weight
    if args.bm25_weight is not None:
        overrides["bm25_weight"] = args.bm25_weight
    if args.top_k is not None:
        overrides["top_k"] = args.top_k
    if args.rerank_backend is not None:
        overrides["rerank_backend"] = args.rerank_backend
    if args.rerank_pool is not None:
        overrides["rerank_pool_size"] = args.rerank_pool
    if args.context_neighbors is not None:
        overrides["context_neighbor_chunks"] = args.context_neighbors
    if overrides:
        merge_profile_dict(profile, overrides)

    try:
        result = run_document_rag(args.doc_path, args.question, profile)
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))


def _import_batch():
    import run_batch_experiments

    return run_batch_experiments


def _import_c2():
    import run_c2_retrieval_ablation

    return run_c2_retrieval_ablation


def _import_score_single():
    import run_score_answer_accuracy

    return run_score_answer_accuracy


def _import_score_c2():
    import run_c2_ablation_answer_accuracy

    return run_c2_ablation_answer_accuracy


def cmd_experiment_batch(args: argparse.Namespace) -> None:
    _import_batch().run_batch_from_limit(args.limit)


def cmd_experiment_c2(args: argparse.Namespace) -> None:
    _import_c2().run_c2_ablation_from_args(args)


def cmd_score_answers(args: argparse.Namespace) -> None:
    _import_score_single().run_score_answer_from_args(args)


def cmd_score_c2_ablation(args: argparse.Namespace) -> None:
    _import_score_c2().run_c2_ablation_accuracy_from_args(args)


def cmd_demo_interactive(args: argparse.Namespace) -> None:
    demos.run_interactive_demo(args.doc_path)


def cmd_demo_once(args: argparse.Namespace) -> None:
    print(demos.run_single_shot_rag(args.doc_path, args.question, top_k=args.top_k))


def cmd_demo_c1(args: argparse.Namespace) -> None:
    result = demos.run_c1_rewrite_once(
        args.doc_path,
        args.question,
        top_k=args.top_k,
        log_dir=args.log_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_ui(args: argparse.Namespace) -> None:
    demos.launch_gradio_ui(host=args.host)


def cmd_hub(_args: argparse.Namespace) -> None:
    """与无参数启动相同：集成工作台。"""
    run_integrated_hub()


def cmd_session_init(_args: argparse.Namespace) -> None:
    p = interactive_configure_session()
    path = save_session_from_profile(p)
    print(f"\n[session] 已写入本地运行偏好：{path}")
    print("说明：这是磁盘上的 YAML 配置，不是模型的对话记忆。")
    print("工作台 [4] 或 `main.py rag …` 将自动合并上述开关（`-c` 与 CLI 可覆盖）。")


def cmd_session_show(_args: argparse.Namespace) -> None:
    path = default_session_path()
    if not path.is_file():
        print("尚无配置文件。请在工作台选 [1]，或：uv run python main.py session init")
        print("也可复制 configs/active_session.example.yaml → configs/active_session.yaml")
        return
    print(path.resolve())
    print()
    print(path.read_text(encoding="utf-8"))


def cmd_agent(args: argparse.Namespace) -> None:
    from agentic_rag.deep_planning.agent_cli import cmd_agent as run_deep_agent

    run_deep_agent(args)


def cmd_kb_ingest(args: argparse.Namespace) -> None:
    from agentic_rag.experiment.kb_ingest import ingest_local_file_to_kb

    path = Path(args.path).expanduser().resolve()
    r = ingest_local_file_to_kb(
        config.PROJECT_ROOT,
        path,
        title=getattr(args, "title", None),
        doc_type=str(getattr(args, "doc_type", "user_doc") or "user_doc"),
        source_note=str(getattr(args, "source_note", "") or "").strip() or "CLI 入库",
        note=str(getattr(args, "note", "") or ""),
        copy_file=not bool(getattr(args, "no_copy", False)),
        force_rebuild_index=not bool(getattr(args, "no_rebuild", False)),
    )
    print(json.dumps(r, ensure_ascii=False, indent=2))
    if not r.get("ok"):
        sys.exit(1)


def cmd_session_clear(_args: argparse.Namespace) -> None:
    path = default_session_path()
    if path.is_file():
        path.unlink()
        print(f"[session] 已删除配置文件 {path}")
    else:
        print("[session] 无配置文件，无需清除")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Topic4 Agentic RAG Evaluation — 统一入口（无参数 = 集成工作台）",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    p_hub = sub.add_parser(
        "hub",
        help="集成工作台：会话配置 + 批量/消融/评判/RAG/测试（与无参数启动相同）",
    )
    p_hub.set_defaults(func=cmd_hub)

    p_chat = sub.add_parser("chat", help="仅 DeepSeek 对话（无 RAG）")
    p_chat.add_argument("--prompt", "-p", metavar="TEXT", help="非交互：直接传入一句话")
    p_chat.set_defaults(func=cmd_chat)

    p_rag = sub.add_parser(
        "rag",
        help="单文档 RAG（默认：Chroma + 混合检索 + C1 rewrite）",
    )
    p_rag.add_argument("doc_path", help="本地文档路径")
    p_rag.add_argument("question", help="用户问题")
    p_rag.add_argument("--config", "-c", type=Path, metavar="YAML", default=None)
    p_rag.add_argument("--no-chroma", action="store_true")
    p_rag.add_argument("--no-hybrid", action="store_true")
    p_rag.add_argument("--no-rewrite", action="store_true")
    p_rag.add_argument("--log", action="store_true")
    p_rag.add_argument("--question-id", default="")
    p_rag.add_argument("--dense-weight", type=float, default=None)
    p_rag.add_argument("--bm25-weight", type=float, default=None)
    p_rag.add_argument("--top-k", type=int, default=None, metavar="K")
    p_rag.add_argument("--rerank", action="store_true")
    p_rag.add_argument("--no-rerank", action="store_true")
    p_rag.add_argument("--rerank-backend", default=None, metavar="NAME")
    p_rag.add_argument("--rerank-pool", type=int, default=None, metavar="N")
    p_rag.add_argument("--context-neighbors", type=int, default=None, metavar="N")
    p_rag.set_defaults(func=cmd_rag)

    sub.add_parser(
        "agent",
        parents=[build_agent_parser(add_help=False)],
        help="Deep Agents 动态规划 + Topic4 RAG 工具（需 uv sync --group agent）",
    ).set_defaults(func=cmd_agent)

    exp = sub.add_parser("experiment", help="批量 / 消融（与既有脚本等价）")
    exp_sub = exp.add_subparsers(dest="exp_cmd", metavar="SUB", required=True)

    exp_sub.add_parser(
        "batch",
        parents=[_import_batch().build_batch_parser(add_help=False)],
        help="C0/C1 批量（runs/results/c0_results.csv 等）",
    ).set_defaults(func=cmd_experiment_batch)

    exp_sub.add_parser(
        "c2",
        parents=[_import_c2().build_c2_ablation_parser(add_help=False)],
        help="C2 三阶段检索消融",
    ).set_defaults(func=cmd_experiment_c2)

    score = sub.add_parser("score", help="答案评判与 C2 汇总")
    score_sub = score.add_subparsers(dest="score_cmd", metavar="SUB", required=True)

    score_sub.add_parser(
        "answers",
        parents=[_import_score_single().build_score_answer_parser(add_help=False)],
        help="单份 *_results.csv → *_scored.csv",
    ).set_defaults(func=cmd_score_answers)

    score_sub.add_parser(
        "c2-ablation",
        parents=[_import_score_c2().build_c2_accuracy_parser(add_help=False)],
        help="C2 三阶段 CSV 批量评判 + 汇总 JSON/Markdown",
    ).set_defaults(func=cmd_score_c2_ablation)

    demo = sub.add_parser("demo", help="旧独立 demo 脚本入口（逻辑在 cli/demos.py）")
    demo_sub = demo.add_subparsers(dest="demo_cmd", metavar="SUB", required=True)

    d_i = demo_sub.add_parser("interactive", help="同旧 demo.py：循环问答")
    d_i.add_argument("doc_path", nargs="?", default=None, help="可选：首次指定文档路径")
    d_i.set_defaults(func=cmd_demo_interactive)

    d_o = demo_sub.add_parser("once", help="同旧 rag_demo.py：单次问答")
    d_o.add_argument("doc_path", help="文档路径")
    d_o.add_argument("question", help="问题")
    d_o.add_argument("--top-k", type=int, default=4, metavar="K")
    d_o.set_defaults(func=cmd_demo_once)

    d_c1 = demo_sub.add_parser("c1", help="同旧 c1_rewrite_demo.py：打印 JSON")
    d_c1.add_argument("doc_path", help="文档路径")
    d_c1.add_argument("question", help="问题")
    d_c1.add_argument("--top-k", type=int, default=5, metavar="K")
    d_c1.add_argument("--log-dir", default="runs/logs", help="JSONL 日志目录")
    d_c1.set_defaults(func=cmd_demo_c1)

    p_ui = sub.add_parser("ui", help="同旧 upload_demo.py：Gradio 上传问答")
    p_ui.add_argument("--host", default="127.0.0.1", help="监听地址")
    p_ui.set_defaults(func=cmd_ui)

    sess = sub.add_parser(
        "session",
        help="运行偏好（非模型记忆）：读写 configs/active_session.yaml；rag 自动合并",
    )
    sess_sub = sess.add_subparsers(dest="session_cmd", metavar="SUB", required=True)
    sess_sub.add_parser(
        "init",
        help="交互选择 Chroma / 混合检索 / 改写 / rerank / 上下文扩展等并保存",
    ).set_defaults(func=cmd_session_init)
    sess_sub.add_parser(
        "show",
        help="显示当前会话文件路径与内容",
    ).set_defaults(func=cmd_session_show)
    sess_sub.add_parser(
        "clear",
        help="删除会话文件（下次 rag 恢复内置默认）",
    ).set_defaults(func=cmd_session_clear)

    kb = sub.add_parser(
        "kb",
        help="知识库清单与增量入库（documents.csv + Chroma 全库索引）",
    )
    kb_sub = kb.add_subparsers(dest="kb_cmd", metavar="SUB", required=True)
    p_kb_ingest = kb_sub.add_parser(
        "ingest",
        help="复制文件到 data/raw/user_docs/、写入清单并重建向量索引",
    )
    p_kb_ingest.add_argument(
        "path",
        type=Path,
        help="待入库的本地文件（建议 UTF-8 文本/Markdown）",
    )
    p_kb_ingest.add_argument("--title", default=None, help="清单标题（默认取文件名）")
    p_kb_ingest.add_argument(
        "--doc-type",
        default="user_doc",
        help="documents.csv 中的 doc_type，默认 user_doc",
    )
    p_kb_ingest.add_argument("--note", default="", help="备注列")
    p_kb_ingest.add_argument(
        "--source-note",
        default="CLI 入库",
        help="来源说明（写入 source 列）",
    )
    p_kb_ingest.add_argument(
        "--no-copy",
        action="store_true",
        help="不复制：CSV 登记为仓库内相对路径（文件须已在工程目录下）",
    )
    p_kb_ingest.add_argument(
        "--no-rebuild",
        action="store_true",
        help="仅更新 CSV（不重建切块与 Chroma；下一次检索或手动重建才会量化）",
    )
    p_kb_ingest.set_defaults(func=cmd_kb_ingest)

    return parser


def main(argv: list[str] | None = None) -> None:
    argv_in = argv if argv is not None else sys.argv[1:]
    if not argv_in:
        run_integrated_hub()
        return

    parser = build_parser()
    args = parser.parse_args(argv_in)
    args.func(args)


if __name__ == "__main__":
    main()
