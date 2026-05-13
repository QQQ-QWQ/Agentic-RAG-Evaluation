"""runner：全库 RAG 在无 documents.csv 时的错误路径。"""

from pathlib import Path

from agentic_rag.experiment.runner import run_knowledge_base_rag


def test_kb_rag_missing_inventory(tmp_path: Path) -> None:
    r = run_knowledge_base_rag("test question", project_root=tmp_path)
    assert r.get("error")
    assert "documents.csv" in r["error"]
