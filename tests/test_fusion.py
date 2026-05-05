from agentic_rag.rag.fusion import fuse_dense_bm25, min_max_normalize, normalize_weights


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
