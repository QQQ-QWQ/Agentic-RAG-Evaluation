"""deep_planning.presets 无可选依赖，应在默认 CI 下通过。"""

from agentic_rag.deep_planning.presets import (
    list_preset_ids,
    run_profile_for_preset,
)


def test_presets_are_disjoint_copies() -> None:
    a = run_profile_for_preset("c0_naive")
    b = run_profile_for_preset("c0_naive")
    assert a.use_query_rewrite is False
    assert a.use_hybrid_retrieval is False
    a.use_query_rewrite = True
    assert b.use_query_rewrite is False


def test_c2_progression() -> None:
    s1 = run_profile_for_preset("c2_stage1_hybrid")
    s2 = run_profile_for_preset("c2_stage2_rerank")
    s3 = run_profile_for_preset("c2_stage3_context")
    assert s1.use_rerank is False and s1.context_neighbor_chunks == 0
    assert s2.use_rerank is True and s2.context_neighbor_chunks == 0
    assert s3.use_rerank is True and s3.context_neighbor_chunks >= 1


def test_list_preset_ids_stable() -> None:
    ids = list_preset_ids()
    assert "project_default" in ids and "c2_stage3_context" in ids
