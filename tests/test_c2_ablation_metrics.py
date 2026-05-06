from agentic_rag.experiment.c2_ablation_metrics import (
    gold_chunk_rank,
    gold_chunk_status,
    summarize_variant,
)


def test_gold_chunk_pending():
    assert gold_chunk_status(None, []) == "pending"
    assert gold_chunk_status({"evidence_chunk_id": "pending"}, ["a"]) == "pending"
    assert gold_chunk_status({"evidence_chunk_id": ""}, ["a"]) == "pending"


def test_gold_chunk_hit():
    ref = {"evidence_chunk_id": "doc_001::chunk_0003"}
    assert gold_chunk_status(ref, ["doc_001::chunk_0003"]) == "true"
    assert gold_chunk_status(ref, ["other"]) == "false"
    assert gold_chunk_rank(ref, ["x", "doc_001::chunk_0003"]) == "2"


def test_summarize_variant_empty():
    assert summarize_variant([])["n_questions"] == 0
