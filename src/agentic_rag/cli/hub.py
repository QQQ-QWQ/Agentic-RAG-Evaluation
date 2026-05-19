"""集成工作台：配置、单文档 RAG、C3/C4 客户端入口。

顶层不 import ``app``，避免循环引用；菜单项内延迟导入。
"""

from __future__ import annotations

import argparse


def run_integrated_hub() -> None:
    """交互循环：配置 → 单文档 RAG → C3/C4 客户端。"""
    print(
        """
================================================================
  Topic4 — 集成工作台
  [1] 运行偏好（configs/active_session.yaml）
  [4] 单文档 RAG（C0/C1 管线，非 Agent）
  [5] C3/C4 客户端（全库 / 附加 / 组合检索 + 选档）
  [6] 日志查看（知识库状态 / 会话对话 / 审计）
  批量实验：python main.py experiment batch | experiment c2 | score …
================================================================"""
    )

    while True:
        print(
            """
  [1] 配置接入模块与运行偏好（configs/active_session.yaml）
  [2] 查看当前配置
  [3] 清除配置文件
  [4] 单文档 RAG（路径 + 问题，遵循 [1]）
  [5] 启动 C3/C4 客户端（Gradio 或终端）
  [6] 日志查看（Gradio）
  [0] 退出
"""
        )
        try:
            choice = input("请选择 > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            break

        if choice in ("0", "q", "quit", "exit"):
            print("再见。")
            break

        try:
            if choice == "1":
                _hub_session_init()
            elif choice == "2":
                _hub_session_show()
            elif choice == "3":
                _hub_session_clear()
            elif choice == "4":
                _hub_rag()
            elif choice == "5":
                _hub_c34_client()
            elif choice == "6":
                _hub_logs()
            else:
                print("无效选项，请重新输入。")
        except KeyboardInterrupt:
            print("\n（已取消）\n")
        except Exception as exc:
            print(f"\n[错误] {exc}\n")


def _hub_session_init() -> None:
    from agentic_rag.cli.app import cmd_session_init

    cmd_session_init(argparse.Namespace())


def _hub_session_show() -> None:
    from agentic_rag.cli.app import cmd_session_show

    cmd_session_show(argparse.Namespace())


def _hub_session_clear() -> None:
    from agentic_rag.cli.app import cmd_session_clear

    cmd_session_clear(argparse.Namespace())


def _hub_rag() -> None:
    from agentic_rag.cli.app import cmd_rag

    doc = input("文档路径: ").strip().strip('"')
    q = input("问题: ").strip()
    if not doc or not q:
        print("路径或问题为空，已跳过。")
        return
    ns = argparse.Namespace(
        doc_path=doc,
        question=q,
        config=None,
        no_chroma=False,
        no_hybrid=False,
        no_rewrite=False,
        log=False,
        question_id="",
        dense_weight=None,
        bm25_weight=None,
        top_k=None,
        rerank=False,
        no_rerank=False,
        rerank_backend=None,
        rerank_pool=None,
        context_neighbors=None,
    )
    cmd_rag(ns)


def _hub_c34_client() -> None:
    from agentic_rag.cli.c34_client import (
        RETRIEVAL_MODE_LABELS,
        _prompt_c34_mode_console,
        _prompt_retrieval_scope_console,
        launch_c34_gradio_client,
        normalize_retrieval_mode,
        run_c34_console_client,
    )
    from agentic_rag.documents.multi_doc import RETRIEVAL_FULL_KB

    print(
        "\n"
        "------------------------------------------------------------\n"
        "  启动方式\n"
        "------------------------------------------------------------\n"
        "  [1] 浏览器 Gradio（默认）\n"
        "  [2] 终端多行对话（输入 END 结束一轮）\n"
    )
    try:
        ui = input("请选择 (1/2，默认 1): ").strip() or "1"
    except (EOFError, KeyboardInterrupt):
        print("\n已取消。")
        return

    enable_c4, enable_sbx = _prompt_c34_mode_console()

    print(
        "\n附加文件路径（每行一个；不附加请 **连按两次回车**；已有路径时空行结束）：\n"
        "  示例：data/raw/session_upload/notes.md\n"
    )
    lines: list[str] = []
    blank_streak = 0
    while True:
        try:
            line = input()
        except (EOFError, KeyboardInterrupt):
            print("\n已取消。")
            return
        if not line.strip():
            blank_streak += 1
            if lines:
                break
            if blank_streak >= 2:
                break
            print("  （仅查系统全库：再按一次回车继续）")
            continue
        blank_streak = 0
        lines.append(line.strip())
    paths_text = "\n".join(lines)
    has_attachments = bool(paths_text.strip())

    retrieval_mode = RETRIEVAL_FULL_KB
    if has_attachments:
        retrieval_mode = _prompt_retrieval_scope_console(has_attachments=True)
    print(f"\n检索范围：{RETRIEVAL_MODE_LABELS.get(retrieval_mode, retrieval_mode)}\n")

    retrieval_mode = normalize_retrieval_mode(
        retrieval_mode,
        has_attachments=has_attachments,
    )

    if ui == "2":
        run_c34_console_client(
            doc_path=paths_text or None,
            enable_c4=enable_c4,
            enable_sandbox=enable_sbx,
            retrieval_mode=retrieval_mode,
        )
    else:
        print(
            "\n正在启动 Gradio… 浏览器将打开 http://127.0.0.1:7860\n"
            "  请在页面点击「开始会话」后再提问；关闭终端窗口即停止服务。\n"
        )
        launch_c34_gradio_client(
            host="127.0.0.1",
            default_enable_c4=enable_c4,
            default_enable_sandbox=enable_sbx,
            default_retrieval_mode=retrieval_mode,
            default_doc_paths_text=paths_text,
        )


def _hub_logs() -> None:
    from agentic_rag.cli.logs_viewer import launch_logs_gradio

    print("\n正在启动日志查看 Gradio（http://127.0.0.1:7860）…\n")
    launch_logs_gradio(host="127.0.0.1")
