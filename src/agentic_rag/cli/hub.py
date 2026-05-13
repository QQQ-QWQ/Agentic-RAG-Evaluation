"""集成工作台：单一入口；模块开关与运行偏好仅在 [1] 配置，[4] RAG 仅消费该配置。

顶层不 import ``app``，避免循环引用；菜单项内延迟导入。
"""

from __future__ import annotations

import argparse


def run_integrated_hub() -> None:
    """交互循环：配置 → 查看/清除 → 单文档 RAG（无批量实验菜单）。"""
    print(
        """
================================================================
  Topic4 — 集成工作台
  [1] 为唯一配置入口（本地 YAML，非大模型记忆）
  [4] 单文档 RAG 只读取 [1] 的配置；批量/消融/评判请用命令行：
      python main.py experiment batch | experiment c2 | score …
================================================================"""
    )

    while True:
        print(
            """
  [1] 配置接入模块与运行偏好（configs/active_session.yaml）
  [2] 查看当前配置
  [3] 清除配置文件
  [4] 单文档 RAG（路径 + 问题，遵循 [1]）
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
