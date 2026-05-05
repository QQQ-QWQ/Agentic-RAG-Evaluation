"""
Topic4 仓库最外层入口：在此汇总 CLI 能力（子命令），避免能力散落在多个 demo 脚本。

- 无子命令：与旧版相同，交互式「仅 DeepSeek、不经 RAG」。
- ``chat``：仅对话。
- ``rag``：单文档结构化 RAG（``RunProfile`` + ``run_document_rag``），默认 Chroma + 混合检索 + C1 rewrite。

新功能请在 ``src/agentic_rag/`` 实现 → ``experiment/runner.py`` 接线 → 在此 ``rag`` 子命令增加参数。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agentic_rag import config
from agentic_rag.experiment import (
    RunProfile,
    load_profile_yaml,
    merge_profile_dict,
    run_document_rag,
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
    if args.config:
        profile = load_profile_yaml(Path(args.config))
    else:
        profile = RunProfile()

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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Topic4 Agentic RAG Evaluation — 统一入口（chat / rag）",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    p_chat = sub.add_parser("chat", help="仅 DeepSeek 对话（无 RAG）")
    p_chat.add_argument(
        "--prompt",
        "-p",
        metavar="TEXT",
        help="非交互：直接传入一句话",
    )
    p_chat.set_defaults(func=cmd_chat)

    p_rag = sub.add_parser(
        "rag",
        help="单文档 RAG（默认：Chroma + 混合检索 + C1 rewrite；可用开关关闭模块）",
    )
    p_rag.add_argument("doc_path", help="本地文档路径")
    p_rag.add_argument("question", help="用户问题")
    p_rag.add_argument(
        "--config",
        "-c",
        type=Path,
        metavar="YAML",
        help="覆盖默认 RunProfile（如 configs/run_default.yaml）",
    )
    p_rag.add_argument("--no-chroma", action="store_true", help="禁用 Chroma")
    p_rag.add_argument(
        "--no-hybrid",
        action="store_true",
        help="禁用 BM25，仅稠密向量检索",
    )
    p_rag.add_argument(
        "--no-rewrite",
        action="store_true",
        help="禁用 query rewrite，走 C0",
    )
    p_rag.add_argument("--log", action="store_true", help="写入 runs/logs JSONL")
    p_rag.add_argument("--question-id", default="", help="问题编号（评测追溯）")
    p_rag.add_argument("--dense-weight", type=float, default=None)
    p_rag.add_argument("--bm25-weight", type=float, default=None)
    p_rag.add_argument("--top-k", type=int, default=None, metavar="K")
    p_rag.add_argument(
        "--rerank",
        action="store_true",
        help="启用检索后重排（默认关闭；亦可 YAML use_rerank）",
    )
    p_rag.add_argument(
        "--no-rerank",
        action="store_true",
        help="显式关闭重排",
    )
    p_rag.add_argument(
        "--rerank-backend",
        default=None,
        metavar="NAME",
        help="none（按粗检分数截断）或 llm（默认）",
    )
    p_rag.add_argument(
        "--rerank-pool",
        type=int,
        default=None,
        metavar="N",
        help="重排候选池大小（不小于 top_k）",
    )
    p_rag.add_argument(
        "--context-neighbors",
        type=int,
        default=None,
        metavar="N",
        help="每条命中块向两侧扩展的相邻切块数量（0 关闭）",
    )
    p_rag.set_defaults(func=cmd_rag)

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command is None:
        cmd_chat(argparse.Namespace(prompt=None))
        return

    args.func(args)


if __name__ == "__main__":
    main()
