"""稠密检索分数与 BM25 分数的归一化与加权融合（用于混合检索）。"""

from __future__ import annotations


def min_max_normalize(values: list[float]) -> list[float]:
    """将分数缩放到 [0, 1]；全相等时退化为 0.5（无区分度）。"""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi - lo < 1e-12:
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def normalize_weights(w_dense: float, w_bm25: float) -> tuple[float, float]:
    s = w_dense + w_bm25
    if s <= 0:
        return 0.5, 0.5
    return w_dense / s, w_bm25 / s


def fuse_dense_bm25(
    dense_scores: list[float],
    bm25_scores: list[float],
    *,
    dense_weight: float = 0.6,
    bm25_weight: float = 0.4,
) -> list[float]:
    """
    对两路分数分别做 min-max，再按权重线性组合为综合分。

    ``dense_scores`` / ``bm25_scores`` 须与 chunk 下标一一对应、等长。
    """
    if len(dense_scores) != len(bm25_scores):
        raise ValueError("dense 与 bm25 分数长度须一致")
    wd, wb = normalize_weights(dense_weight, bm25_weight)
    nd = min_max_normalize(dense_scores)
    nb = min_max_normalize(bm25_scores)
    return [wd * d + wb * b for d, b in zip(nd, nb, strict=True)]
