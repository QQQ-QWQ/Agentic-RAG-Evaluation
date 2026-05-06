"""检索后精排：在粗检候选集上重排序，默认 LLM（DeepSeek）打分序。"""

from __future__ import annotations

import json
import re
from typing import Any

from agentic_rag import config
from agentic_rag.llm.deepseek import create_deepseek_client
from agentic_rag.llm.usage_strict import require_deepseek_chat_usage
from agentic_rag.schemas import EvidenceChunk


def _extract_json_array(text: str) -> list[int]:
    text = (text or "").strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [int(x) for x in parsed]
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    m = re.search(r"\[[\s\d,]+\]", text)
    if m:
        try:
            parsed = json.loads(m.group(0))
            if isinstance(parsed, list):
                return [int(x) for x in parsed]
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    raise ValueError("rerank: 无法解析模型输出的 JSON 整数数组")


def rerank_hits(
    query: str,
    hits: list[EvidenceChunk],
    *,
    top_k: int,
    backend: str = "llm",
    max_passage_chars: int = 480,
) -> tuple[list[EvidenceChunk], dict[str, int]]:
    """
    对候选 ``hits`` 重排，保留最相关的 ``top_k`` 条。

    - ``backend=="none"``：按现有 ``score`` 降序截断（不调 API）。
    - ``backend=="llm"``：调用 DeepSeek，要求输出按相关性排序的下标 JSON 数组。
    """
    if not hits or top_k <= 0:
        return [], {}
    if len(hits) <= top_k:
        return hits, {}

    if backend in ("none", "skip", ""):
        ordered = sorted(hits, key=lambda h: h.score, reverse=True)[:top_k]
        return ordered, {}

    if backend != "llm":
        raise ValueError(f"未知 rerank backend: {backend}")

    lines: list[str] = []
    for i, h in enumerate(hits):
        snippet = (h.text or "")[:max_passage_chars].replace("\n", " ")
        lines.append(f"{i}. id={h.chunk_id} | {snippet}")

    user_content = (
        f"Question:\n{query}\n\nPassages indexed 0..{len(hits)-1}:\n"
        + "\n".join(lines)
        + f"\n\nPick the {top_k} most relevant passage indices. "
        f"Output ONLY a JSON array of exactly {top_k} distinct integers, best match first. "
        "Example: [3,0,7]. No markdown."
    )

    client = create_deepseek_client()
    resp = client.chat.completions.create(
        model=config.DEEPSEEK_CHAT_MODEL or "deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": "You only output valid JSON: one array of integers.",
            },
            {"role": "user", "content": user_content},
        ],
        temperature=0.0,
    )
    raw = (resp.choices[0].message.content or "").strip()
    order = _extract_json_array(raw)

    seen: set[int] = set()
    out: list[EvidenceChunk] = []
    for idx in order:
        if len(out) >= top_k:
            break
        if not (0 <= idx < len(hits)) or idx in seen:
            continue
        seen.add(idx)
        h = hits[idx]
        out.append(
            EvidenceChunk(
                chunk_id=h.chunk_id,
                doc_id=h.doc_id,
                text=h.text,
                score=float(top_k - len(out)),
                source=h.source,
                page=h.page,
                rank=len(out) + 1,
                query=h.query,
            )
        )

    if len(out) < top_k:
        rest = sorted(hits, key=lambda h: h.score, reverse=True)
        for h in rest:
            if len(out) >= top_k:
                break
            if any(x.chunk_id == h.chunk_id for x in out):
                continue
            out.append(
                EvidenceChunk(
                    chunk_id=h.chunk_id,
                    doc_id=h.doc_id,
                    text=h.text,
                    score=h.score,
                    source=h.source,
                    page=h.page,
                    rank=len(out) + 1,
                    query=h.query,
                )
            )

    usage = _usage_to_dict(getattr(resp, "usage", None))
    require_deepseek_chat_usage(usage, where="检索重排（rerank）")
    return out[:top_k], usage


def _usage_to_dict(usage: Any) -> dict[str, int]:
    if usage is None:
        return {}
    out: dict[str, int] = {}
    for attr in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = getattr(usage, attr, None)
        if value is not None:
            out[attr] = int(value)
    return out
