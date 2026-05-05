from __future__ import annotations

import json
import sys

from agentic_rag.pipelines import build_vector_index, run_c1_with_index


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit('Usage: uv run python c1_rewrite_demo.py "doc_path" "question"')

    doc_path = sys.argv[1].strip().strip('"')
    question = sys.argv[2].strip()
    index = build_vector_index(doc_path)
    result = run_c1_with_index(index, question, top_k=5, log_dir="runs/logs")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
