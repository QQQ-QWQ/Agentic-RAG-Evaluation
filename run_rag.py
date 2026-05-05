#!/usr/bin/env python3
"""
兼容入口：等价于 ``python main.py rag ...``。

正式联调请使用根目录 ``main.py`` 子命令 ``rag`` / ``chat``。
"""

from __future__ import annotations

import sys


def main() -> None:
    sys.argv = [sys.argv[0], "rag", *sys.argv[1:]]
    from main import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
