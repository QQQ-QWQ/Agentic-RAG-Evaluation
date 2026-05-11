"""
知识库对齐核验：沿用 ``evaluation/ai_answer_judge`` 的思路（DeepSeek + JSON），
用检索得到的证据摘录检验模型最终答复是否「有据可依」。

不等同于题库 rubric 打分；面向编排链路的自检。
"""

from __future__ import annotations

from typing import Any

from agentic_rag import config
from agentic_rag.llm.deepseek import create_deepseek_client
from agentic_rag.llm.usage_strict import require_deepseek_chat_usage
from agentic_rag.rewrite import extract_json_object

KB_GROUNDING_SYSTEM = (
    "你是核查员。给定「用户问题」「检索证据摘录」「模型答复」，判断答复要点是否主要由证据支持。\n"
    "若证据为空或不足以判断，grounded=false。\n"
    "只输出合法 JSON："
    '{"grounded": true/false, "confidence": 0~1 的数字, "issues": "中文简述"}'
)


def run_kb_grounding_check(
    *,
    question: str,
    generated_answer: str,
    evidence_excerpt: str,
    model: str | None = None,
) -> dict[str, Any]:
    """
    返回字段：grounded (bool), confidence (float), issues (str), judge_total_tokens (int)。
    证据为空时直接返回 grounded=false，不调模型。
    """
    ev = (evidence_excerpt or "").strip()
    ans = (generated_answer or "").strip()
    q = (question or "").strip()
    if not ev:
        return {
            "grounded": False,
            "confidence": 0.0,
            "issues": "本轮未捕获检索证据摘录，跳过对齐核验",
            "judge_total_tokens": 0,
            "skipped": True,
        }

    user_msg = (
        f"【用户问题】\n{q}\n\n"
        f"【检索证据摘录】\n{ev[:12000]}\n\n"
        f"【模型答复】\n{ans[:12000]}\n"
    )
    client = create_deepseek_client()
    resp = client.chat.completions.create(
        model=model or config.DEEPSEEK_CHAT_MODEL or "deepseek-chat",
        messages=[
            {"role": "system", "content": KB_GROUNDING_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.0,
    )
    raw = (resp.choices[0].message.content or "").strip()
    usage: dict[str, int] = {}
    u = getattr(resp, "usage", None)
    if u is not None:
        for attr in ("prompt_tokens", "completion_tokens", "total_tokens"):
            v = getattr(u, attr, None)
            if v is not None:
                usage[attr] = int(v)
    require_deepseek_chat_usage(usage, where="知识库对齐核验")

    try:
        payload = extract_json_object(raw)
    except Exception:
        return {
            "grounded": False,
            "confidence": 0.0,
            "issues": "核验 JSON 解析失败",
            "judge_total_tokens": usage.get("total_tokens", 0),
            "skipped": False,
            "parse_error": True,
            "raw": raw[:800],
        }
    grounded = bool(payload.get("grounded", False))
    try:
        confidence = float(payload.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    issues = str(payload.get("issues") or "").strip()
    return {
        "grounded": grounded,
        "confidence": confidence,
        "issues": issues,
        "judge_total_tokens": usage.get("total_tokens", 0),
        "skipped": False,
    }
