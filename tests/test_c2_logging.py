from __future__ import annotations

import json
import sys
from importlib import util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = util.spec_from_file_location(
    "run_c2_retrieval_ablation",
    ROOT / "run_c2_retrieval_ablation.py",
)
assert SPEC is not None
assert SPEC.loader is not None
c2 = util.module_from_spec(SPEC)
SPEC.loader.exec_module(c2)


def test_c2_variant_writes_to_variant_log_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(c2, "LOG_ROOT", tmp_path)
    monkeypatch.setattr(c2, "backup_and_reset_log", lambda config_name: tmp_path / config_name / "run_logs.jsonl")

    def fake_run_c1_with_index(index, question, **kwargs):
        assert kwargs["log_dir"] is None
        return {
            "run_id": "fake-run",
            "config": "c1_rewrite",
            "question_id": kwargs["question_id"],
            "original_query": question,
            "retrieval_queries": [question],
            "retrieved_chunks": [
                {
                    "chunk_id": "doc_001::chunk_0001",
                    "doc_id": "doc_001",
                    "text": "answer evidence",
                    "score": 1.0,
                    "source": "fake.md",
                    "page": None,
                    "rank": 1,
                    "query": question,
                }
            ],
            "answer": "answer",
            "citations": [{"doc_id": "doc_001", "chunk_id": "doc_001::chunk_0001"}],
            "latency_ms": 1,
            "token_usage": {},
            "token_cost": None,
            "error": "",
            "log_path": "",
        }

    monkeypatch.setattr(c2, "run_c1_with_index", fake_run_c1_with_index)

    rows = c2.run_variant(
        variant_key="c2_stage1_c1_hybrid",
        display_name="stage1",
        index=None,
        questions=[
            {
                "question_id": "Q001",
                "question": "question",
                "task_type": "simple_qa",
                "difficulty": "easy",
                "required_tool": "none",
                "expected_path": "C2",
            }
        ],
        references={
            "Q001": {
                "evidence_doc_id": "doc_001",
                "evidence_chunk_id": "doc_001::chunk_0001",
            }
        },
        use_rewrite=True,
        hybrid=True,
        use_rerank=False,
        context_neighbor_chunks=0,
        top_k=5,
        rerank_backend="llm",
        rerank_pool_size=20,
        dense_weight=0.6,
        bm25_weight=0.4,
    )

    log_path = tmp_path / "c2_stage1_c1_hybrid" / "run_logs.jsonl"
    assert log_path.is_file()
    assert rows[0]["log_path"] == str(log_path)

    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["config"] == "c2_stage1_c1_hybrid"
    assert records[0]["log_path"] == str(log_path)
