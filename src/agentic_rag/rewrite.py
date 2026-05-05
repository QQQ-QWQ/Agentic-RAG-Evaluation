from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentic_rag import config
from agentic_rag.llm.deepseek import create_deepseek_client
from agentic_rag.schemas import RewriteResult


DEFAULT_REWRITE_PROMPT = """You are the query diagnosis and rewrite module in a RAG system.

Your task is not to answer the user's question. Your task is to decide whether the
query needs rewriting, then produce a clearer retrieval query when needed.

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
6. Output valid JSON only.

Return this JSON object:
{
  "need_rewrite": true,
  "rewrite_reason": "brief reason",
  "rewritten_query": "clear retrieval query",
  "rewrite_type": "fuzzy_query|colloquial|omitted_subject|mixed_terms|evidence_location|none"
}

User question:
{question}
"""


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


def normalize_rewrite_payload(
    payload: dict[str, Any],
    *,
    original_query: str,
    raw_output: str = "",
    token_usage: dict[str, int] | None = None,
) -> RewriteResult:
    need_rewrite = bool(payload.get("need_rewrite", False))
    rewritten_query = str(payload.get("rewritten_query") or "").strip()
    if not rewritten_query:
        rewritten_query = original_query
        need_rewrite = False

    if rewritten_query.strip() == original_query.strip():
        need_rewrite = False

    rewrite_reason = str(payload.get("rewrite_reason") or "").strip()
    rewrite_type = str(payload.get("rewrite_type") or "none").strip() or "none"
    if not need_rewrite:
        rewrite_type = "none"

    return RewriteResult(
        need_rewrite=need_rewrite,
        rewrite_reason=rewrite_reason,
        rewritten_query=rewritten_query,
        rewrite_type=rewrite_type,
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
    else:
        need_rewrite = bool(rewrite_result.get("need_rewrite", False))
        rewritten_query = str(rewrite_result.get("rewritten_query") or "").strip()

    queries: list[str] = []
    original = original_query.strip()
    rewritten = rewritten_query.strip()
    if keep_original_query and original:
        queries.append(original)
    if need_rewrite and rewritten and rewritten not in queries:
        queries.append(rewritten)
    if not queries and original:
        queries.append(original)
    return queries
