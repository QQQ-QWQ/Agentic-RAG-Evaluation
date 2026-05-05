"""
交互式 RAG：第一次指定文档路径并建索引，之后同一终端里多次提问（不再重复向量化文档）。

用法：
  uv run python demo.py
  uv run python demo.py "D:\\资料\\手册.pdf"
第二步：按提示输入问题；输入空行退出。
"""

from __future__ import annotations

import sys
from agentic_rag import config
from agentic_rag.pipelines import answer_with_index, build_vector_index


def _require_env() -> None:
    if not config.ARK_API_KEY:
        sys.exit("请配置 .env：ARK_API_KEY")
    if not config.DEEPSEEK_API_KEY:
        sys.exit("请配置 .env：DEEPSEEK_API_KEY")


def main() -> None:
    _require_env()

    if len(sys.argv) >= 2:
        doc_path = sys.argv[1].strip().strip('"')
    else:
        doc_path = input("请输入文档路径: ").strip().strip('"')

    if not doc_path:
        sys.exit("未指定文档路径")

    print("正在解析文档并建立向量索引…")
    index = build_vector_index(doc_path)
    n = len(index.chunks)
    print(f"索引完成，共 {n} 个文本块。随后可直接提问（仅问题会向量化，文档不重复索引）。")
    print("输入空行退出。\n")

    while True:
        try:
            q = input("问题> ").strip()
        except EOFError:
            break
        if not q:
            break
        try:
            ans = answer_with_index(index, q, top_k=4)
        except Exception as e:
            print(f"出错：{e}\n")
            continue
        print(ans)
        print()


if __name__ == "__main__":
    main()
