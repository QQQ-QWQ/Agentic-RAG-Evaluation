from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentic_rag import config
from agentic_rag.llm.deepseek import create_deepseek_client
from agentic_rag.schemas import RewriteResult


DEFAULT_REWRITE_PROMPT = """You are the query diagnosis and rewrite module in a RAG system.

Your task is not to answer the user's question. Your task is to decide whether
the query needs rewriting, then produce retrieval-oriented search queries when
needed.

Focus on these cases:
- vague, colloquial, incomplete, or non-standard expressions;
- omitted subject or unclear reference;
- mixed Chinese and English terms;
- questions that need evidence location or cross-document comparison.

Rules:
1. Preserve the original user intent.
2. Do not add a new goal that the user did not ask for.
3. Do not answer the question.
4. If the original question is already clear, keep it unchanged.
5. Preserve code identifiers, numbers, formulas, file names, and proper nouns.
6. Rewrite for retrieval, not conversation. Prefer compact keyword-rich search
   queries over complete polite questions.
7. Do not introduce new proper nouns, paper names, methods, or aliases unless
   they already appear in the user query.
8. If rewriting would only paraphrase a clear query, set need_rewrite=false.
9. Output valid JSON only.

Return this JSON object:
{
  "need_rewrite": true,
  "rewrite_confidence": 0.0,
  "rewrite_reason": "brief reason",
  "rewrite_type": "fuzzy_query|colloquial|omitted_subject|mixed_terms|evidence_location|multi_doc_comparison|none",
  "rewritten_query": "the best single retrieval query",
  "rewritten_queries": [
    "semantic retrieval query",
    "keyword retrieval query",
    "entity/file/code focused retrieval query if useful"
  ]
}

When need_rewrite=false:
- rewrite_confidence should be 0.4 or lower;
- rewritten_query must equal the original question;
- rewritten_queries must be an empty list.

User question:
{question}
"""

MIN_REWRITE_CONFIDENCE = 0.55
MAX_REWRITTEN_QUERIES = 4


def load_prompt_template(prompt_file: str | Path | None = None) -> str:
    if prompt_file is None:
        return DEFAULT_REWRITE_PROMPT
    path = Path(prompt_file)
    if not path.is_file():
        return DEFAULT_REWRITE_PROMPT
    return path.read_text(encoding="utf-8")


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end < start:
            raise
        parsed = json.loads(cleaned[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("rewrite output must be a JSON object")
    return parsed


def _dedupe_queries(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for query in queries:
        cleaned = str(query or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def _payload_query_list(payload: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    for key in ("rewritten_queries", "candidate_queries", "retrieval_queries"):
        value = payload.get(key)
        if isinstance(value, list):
            candidates.extend(str(item) for item in value)
    for key in ("semantic_query", "keyword_query", "entity_query"):
        value = payload.get(key)
        if value:
            candidates.append(str(value))
    return _dedupe_queries(candidates)


def _rewrite_confidence(payload: dict[str, Any], *, need_rewrite: bool) -> float:
    value = payload.get("rewrite_confidence", None)
    if value is None:
        return 0.8 if need_rewrite else 0.0
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.8 if need_rewrite else 0.0
    return max(0.0, min(1.0, confidence))


def normalize_rewrite_payload(
    payload: dict[str, Any],
    *,
    original_query: str,
    raw_output: str = "",
    token_usage: dict[str, int] | None = None,
) -> RewriteResult:
    need_rewrite = bool(payload.get("need_rewrite", False))
    rewrite_confidence = _rewrite_confidence(payload, need_rewrite=need_rewrite)
    rewritten_query = str(payload.get("rewritten_query") or "").strip()
    rewritten_queries = _payload_query_list(payload)
    if rewritten_query:
        rewritten_queries = _dedupe_queries([rewritten_query, *rewritten_queries])

    if not rewritten_query:
        rewritten_query = original_query
        need_rewrite = False

    rewritten_queries = [
        query
        for query in rewritten_queries
        if query.strip() != original_query.strip()
    ][:MAX_REWRITTEN_QUERIES]
    if rewritten_query.strip() == original_query.strip() and rewritten_queries:
        rewritten_query = rewritten_queries[0]

    if (
        rewritten_query.strip() == original_query.strip()
        or not rewritten_queries
        or rewrite_confidence < MIN_REWRITE_CONFIDENCE
    ):
        need_rewrite = False

    rewrite_reason = str(payload.get("rewrite_reason") or "").strip()
    rewrite_type = str(payload.get("rewrite_type") or "none").strip() or "none"
    if not need_rewrite:
        rewrite_type = "none"
        rewrite_confidence = min(rewrite_confidence, 0.4)
        rewritten_query = original_query
        rewritten_queries = []

    return RewriteResult(
        need_rewrite=need_rewrite,
        rewrite_reason=rewrite_reason,
        rewritten_query=rewritten_query,
        rewrite_type=rewrite_type,
        rewritten_queries=rewritten_queries,
        rewrite_confidence=rewrite_confidence,
        raw_output=raw_output,
        token_usage=token_usage or {},
    )


def usage_to_dict(usage: Any) -> dict[str, int]:
    if usage is None:
        return {}
    out: dict[str, int] = {}
    for attr in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = getattr(usage, attr, None)
        if value is not None:
            out[attr] = int(value)
    return out


def rewrite_query(
    question: str,
    *,
    prompt_file: str | Path | None = None,
    model: str | None = None,
    temperature: float = 0.0,
) -> RewriteResult:
    original_query = question.strip()
    if not original_query:
        return RewriteResult(
            need_rewrite=False,
            rewrite_reason="empty query",
            rewritten_query="",
        )

    prompt_template = load_prompt_template(prompt_file)
    prompt = prompt_template.replace("{question}", original_query)

    client = create_deepseek_client()
    response = client.chat.completions.create(
        model=model or config.DEEPSEEK_CHAT_MODEL or "deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": "Return valid JSON only. Do not answer the user question.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
    )
    raw_output = (response.choices[0].message.content or "").strip()
    payload = extract_json_object(raw_output)
    return normalize_rewrite_payload(
        payload,
        original_query=original_query,
        raw_output=raw_output,
        token_usage=usage_to_dict(getattr(response, "usage", None)),
    )


def build_retrieval_queries(
    original_query: str,
    rewrite_result: RewriteResult | dict[str, Any],
    *,
    keep_original_query: bool = True,
) -> list[str]:
    if isinstance(rewrite_result, RewriteResult):
        need_rewrite = rewrite_result.need_rewrite
        rewritten_query = rewrite_result.rewritten_query
        rewritten_queries = rewrite_result.rewritten_queries
    else:
        need_rewrite = bool(rewrite_result.get("need_rewrite", False))
        rewritten_query = str(rewrite_result.get("rewritten_query") or "").strip()
        rewritten_queries = _payload_query_list(rewrite_result)
        if rewritten_query:
            rewritten_queries = _dedupe_queries([rewritten_query, *rewritten_queries])

    queries: list[str] = []
    original = original_query.strip()
    rewritten = rewritten_query.strip()
    if keep_original_query and original:
        queries.append(original)
    if need_rewrite:
        for candidate in _dedupe_queries([rewritten, *rewritten_queries]):
            if candidate and candidate not in queries:
                queries.append(candidate)
    if not queries and original:
        queries.append(original)
    return queries
