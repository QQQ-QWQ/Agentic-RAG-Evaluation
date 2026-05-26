from dataclasses import dataclass

from agentic_rag.rag.fusion import (
    fuse_dense_bm25,
    min_max_normalize,
    normalize_weights,
    reciprocal_rank_fusion,
)


@dataclass(frozen=True)
class _Hit:
    chunk_id: str
    score: float
    rank: int = 0


def test_min_max_normalize():
    assert min_max_normalize([0.0, 0.5, 1.0]) == [0.0, 0.5, 1.0]
    assert min_max_normalize([2.0, 2.0, 2.0]) == [0.5, 0.5, 0.5]


def test_normalize_weights():
    assert normalize_weights(0.6, 0.4) == (0.6, 0.4)
    a, b = normalize_weights(3.0, 7.0)
    assert abs(a - 0.3) < 1e-9 and abs(b - 0.7) < 1e-9


def test_fuse_dense_bm25_monotonic_dense():
    dense = [1.0, 0.5, 0.0]
    bm25 = [0.0, 0.5, 1.0]
    fused = fuse_dense_bm25(dense, bm25, dense_weight=1.0, bm25_weight=0.0)
    assert fused[0] > fused[1] > fused[2]


def test_reciprocal_rank_fusion_deduplicates_and_prefers_repeated_hits():
    groups = [
        [_Hit("a", 0.2), _Hit("b", 0.9)],
        [_Hit("b", 0.3), _Hit("c", 0.8)],
    ]

    fused = reciprocal_rank_fusion(groups, top_k=2, rrf_k=60)

    assert [hit.chunk_id for hit in fused] == ["b", "a"]
    assert fused[0].rank == 1
