"""CLI 入口分流：fast-path 最小加载，其余动态导入主流程。"""

from __future__ import annotations

import sys
from typing import Callable

from agentic_rag.runtime.tracing import TraceCollector

_EXIT_OK = 0
_EXIT_USAGE = 2
_EXIT_RUNTIME = 1

# fast-path 命令映射：argv 片段 -> 处理函数
FAST_PATH_HANDLERS: dict[str, Callable[[list[str]], int]] = {}


def _register(name: str):
    def deco(fn: Callable[[list[str]], int]):
        FAST_PATH_HANDLERS[name] = fn
        return fn

    return deco


@_register("--version")
@_register("-V")
def _cmd_version(_argv: list[str]) -> int:
    print("agentic-rag-evaluation topic4 runtime 0.1.0")
    return _EXIT_OK


@_register("version")
def _cmd_version_sub(argv: list[str]) -> int:
    return _cmd_version(argv)


def _match_fast_path(argv: list[str]) -> Callable[[list[str]], int] | None:
    if not argv:
        return None
    if argv[0] in FAST_PATH_HANDLERS:
        return FAST_PATH_HANDLERS[argv[0]]
    if len(argv) >= 2 and argv[0] == "runtime" and argv[1] in FAST_PATH_HANDLERS:
        return FAST_PATH_HANDLERS[argv[1]]
    return None


def try_fast_path(argv: list[str] | None = None) -> int | None:
    """
    若命中 fast-path 则执行并返回退出码；否则返回 None 表示应走主流程。
    """
    args = list(argv if argv is not None else sys.argv[1:])
    trace = TraceCollector()
    trace.mark("cli_entry", argv=args[:3])

    handler = _match_fast_path(args)
    if handler is None:
        return None

    trace.mark("fast_path_exec", handler=handler.__name__)
    try:
        code = handler(args)
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return _EXIT_RUNTIME
    for row in trace.as_events():
        if row.get("name") in ("cli_entry", "fast_path_exec"):
            print(f"[profile] {row['name']} {row['elapsed_ms']}ms", file=sys.stderr)
    return code


def route_to_main(argv: list[str] | None = None) -> int:
    """非 fast-path：动态导入并执行 runtime main 或回落到 Topic4 CLI。"""
    args = list(argv if argv is not None else sys.argv[1:])
    trace = TraceCollector()
    trace.mark("cli_entry", argv=args[:3])

    fast = try_fast_path(args)
    if fast is not None:
        return fast

    trace.mark("before_main_import")
    if args and args[0] == "runtime":
        from agentic_rag.runtime.entrypoints.main import run_runtime_main

        trace.mark("after_main_import")
        code = run_runtime_main(args[1:], startup_trace=trace)
    else:
        from agentic_rag.cli.app import main as topic4_main

        trace.mark("after_main_import")
        saved = sys.argv
        try:
            sys.argv = [saved[0], *args]
            topic4_main()
            code = 0
        except SystemExit as exc:
            code = int(exc.code) if exc.code is not None else 0
        finally:
            sys.argv = saved

    for row in trace.as_events():
        print(f"[profile] {row['name']} {row['elapsed_ms']}ms", file=sys.stderr)
    return code
