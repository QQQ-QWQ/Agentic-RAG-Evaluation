"""最小向量索引：内存存储 + 余弦相似度 Top-K。"""

from __future__ import annotations

import math
from dataclasses import dataclass


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 80) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    out: list[str] = []
    step = max(chunk_size - overlap, 1)
    start = 0
    while start < len(text):
        out.append(text[start : start + chunk_size])
        start += step
    return out


def cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


@dataclass
class SimpleVectorIndex:
    chunks: list[str]
    vectors: list[list[float]]

    def top_k(self, query_vec: list[float], k: int = 4) -> list[tuple[str, float]]:
        scored = [(c, cosine_sim(query_vec, v)) for c, v in zip(self.chunks, self.vectors)]
        scored.sort(key=lambda x: -x[1])
        return scored[:k]
