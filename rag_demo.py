"""单次命令行 RAG：每次运行完整流程（解析 → 向量索引 → 检索 → DeepSeek）。

用法：uv run python rag_demo.py <文档路径> <问题>
"""

from __future__ import annotations

import sys

from agentic_rag import config
from agentic_rag.pipelines import local_rag_answer


def main() -> None:
    if len(sys.argv) < 3:
        print("用法: uv run python rag_demo.py <文档路径> <问题>", file=sys.stderr)
        sys.exit(1)
    if not config.ARK_API_KEY:
        sys.exit("请配置 .env：ARK_API_KEY")
    if not config.DEEPSEEK_API_KEY:
        sys.exit("请配置 .env：DEEPSEEK_API_KEY")
    path = sys.argv[1]
    question = sys.argv[2]
    print(local_rag_answer(path, question, top_k=4))


if __name__ == "__main__":
    main()
