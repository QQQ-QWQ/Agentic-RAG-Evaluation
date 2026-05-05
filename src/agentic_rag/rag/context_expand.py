"""检索后上下文增强：按 chunk 下标合并邻接块文本（父块/窗口扩展）。"""

from __future__ import annotations

import re

from agentic_rag.rag.simple import SimpleVectorIndex
from agentic_rag.schemas import EvidenceChunk


_CHUNK_TAIL_RE = re.compile(r"::chunk_(\d+)$")


def chunk_index_from_id(chunk_id: str) -> int | None:
    m = _CHUNK_TAIL_RE.search(chunk_id.strip())
    if not m:
        return None
    return int(m.group(1))


def expand_hits_with_neighbors(
    hits: list[EvidenceChunk],
    index: SimpleVectorIndex,
    *,
    neighbors: int,
) -> list[EvidenceChunk]:
    """
    将每条命中文本扩展为「自身 ± neighbors 个相邻切块」的拼接，便于生成时获得更广上下文。

    ``neighbors=0`` 时原样返回。切块顺序与 ``index.chunks`` 一致。
    """
    if neighbors <= 0 or not hits:
        return hits
    n = len(index.chunks)
    if n == 0:
        return hits

    out: list[EvidenceChunk] = []
    for h in hits:
        idx = chunk_index_from_id(h.chunk_id)
        if idx is None:
            out.append(h)
            continue
        lo = max(0, idx - neighbors)
        hi = min(n, idx + neighbors + 1)
        parts = [index.chunks[j] for j in range(lo, hi)]
        merged = "\n\n---\n\n".join(parts)
        out.append(
            EvidenceChunk(
                chunk_id=h.chunk_id,
                doc_id=h.doc_id,
                text=merged,
                score=h.score,
                source=h.source,
                page=h.page,
                rank=h.rank,
                query=h.query,
            )
        )
    return out
