from pathlib import Path

from agentic_rag.experiment.profile import RunProfile, load_profile_yaml, merge_profile_dict


def test_profile_defaults():
    p = RunProfile()
    assert p.use_chroma_cache is True
    assert p.use_hybrid_retrieval is True
    assert p.use_query_rewrite is True


def test_merge_profile_dict():
    p = RunProfile()
    merge_profile_dict(
        p,
        {
            "use_chroma_cache": False,
            "top_k": 3,
            "use_rerank": True,
            "rerank_backend": "NONE",
            "rerank_pool_size": 15,
            "context_neighbor_chunks": 2,
        },
    )
    assert p.use_chroma_cache is False
    assert p.top_k == 3
    assert p.use_rerank is True
    assert p.rerank_backend == "none"
    assert p.rerank_pool_size == 15
    assert p.context_neighbor_chunks == 2


def test_load_yaml_modules(tmp_path: Path):
    yml = tmp_path / "t.yaml"
    yml.write_text(
        """
modules:
  hybrid_retrieval: false
  query_rewrite: true
retrieval:
  top_k: 7
""",
        encoding="utf-8",
    )
    p = load_profile_yaml(yml)
    assert p.use_hybrid_retrieval is False
    assert p.use_query_rewrite is True
    assert p.top_k == 7
