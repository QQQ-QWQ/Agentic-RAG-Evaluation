"""LLM 按题库 rubric 评判生成答案（独立模块，与人评解耦）。

本模块**不**等同于最终「答案是否正确」：输出用于实验流水线中的自动化测试；
最终正确性需人工按同一 ``judge_rule`` 标注后，再与 Machine 分数对比，评估 AI 评判（及后续 AI 自规划/自检链路）的可信度。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentic_rag import config
from agentic_rag.llm.deepseek import create_deepseek_client
from agentic_rag.llm.usage_strict import require_deepseek_chat_usage
from agentic_rag.rewrite import extract_json_object


_SCORE_SET = frozenset({0.0, 0.5, 1.0})


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for p in [here, *here.parents]:
        if (p / "pyproject.toml").is_file():
            return p
    raise RuntimeError("无法定位仓库根目录（缺少 pyproject.toml）")


def _normalize_score(raw: object) -> float:
    try:
        x = float(raw)
    except (TypeError, ValueError):
        return 0.0
    if x in _SCORE_SET:
        return x
    if abs(x - 0.5) < 0.01:
        return 0.5
    if x >= 0.75:
        return 1.0
    if x >= 0.25:
        return 0.5
    return 0.0


def _label_from_score(score: float) -> str:
    if score >= 1.0:
        return "correct"
    if score >= 0.5:
        return "partial"
    return "wrong"


def load_judge_prompt_template(path: str | Path | None = None) -> str:
    """加载 ``prompts/answer_judge_prompt.md`` 或自定义路径。"""
    repo_root = _repo_root()
    p = Path(path) if path else repo_root / "prompts" / "answer_judge_prompt.md"
    if not p.is_file():
        raise FileNotFoundError(f"找不到评判 Prompt 文件: {p}")
    return p.read_text(encoding="utf-8")


def load_rag_judge_prompt_template(path: str | Path | None = None) -> str:
    """Load the multi-dimensional RAG judge prompt template."""
    repo_root = _repo_root()
    p = Path(path) if path else repo_root / "prompts" / "rag_multidim_judge_prompt.md"
    if not p.is_file():
        raise FileNotFoundError(f"Cannot find RAG judge prompt file: {p}")
    return p.read_text(encoding="utf-8")


def _dimension_payload(payload: dict[str, Any], key: str) -> tuple[float, str, str]:
    value = payload.get(key, {})
    if isinstance(value, dict):
        raw_score = value.get("score")
        raw_reason = value.get("reason", "")
    else:
        raw_score = value
        raw_reason = ""
    score = _normalize_score(raw_score)
    return score, _label_from_score(score), str(raw_reason or "").strip()


def judge_answer_with_rule(
    *,
    question: str,
    reference_answer: str,
    generated_answer: str,
    judge_rule: str,
    prompt_file: str | Path | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """
    调用 DeepSeek，按 ``judge_rule`` 返回 ``correctness_score``（0/0.5/1）及用量。

    返回字典字段：
    - ``correctness_score``, ``correctness_label``, ``judge_reason``, ``judge_total_tokens``
    """
    template = load_judge_prompt_template(prompt_file)
    user_content = template.format(
        question=question.strip(),
        reference_answer=(reference_answer or "").strip(),
        generated_answer=(generated_answer or "").strip(),
        judge_rule=(judge_rule or "").strip(),
    )
    client = create_deepseek_client()
    resp = client.chat.completions.create(
        model=model or config.DEEPSEEK_CHAT_MODEL or "deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": "你只输出合法 JSON 对象，严格按用户给的评分规则打分。",
            },
            {"role": "user", "content": user_content},
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
    require_deepseek_chat_usage(usage, where="答案正确率评判")

    payload = extract_json_object(raw)
    score = _normalize_score(payload.get("score"))
    label = str(payload.get("label") or "").strip().lower()
    if label not in ("correct", "partial", "wrong"):
        label = _label_from_score(score)
    reason = str(payload.get("reason") or "").strip()
    return {
        "correctness_score": score,
        "correctness_label": label,
        "judge_reason": reason,
        "judge_total_tokens": usage.get("total_tokens", 0),
    }


def judge_rag_response_with_rubric(
    *,
    question: str,
    reference_answer: str,
    generated_answer: str,
    judge_rule: str,
    retrieved_evidence: str = "",
    generated_citations: str = "",
    gold_doc_id: str = "",
    gold_chunk_id: str = "",
    prompt_file: str | Path | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """
    Score one RAG response with multiple dimensions.

    This is an auxiliary LLM-as-judge path. It does not replace human labels.
    """
    template = load_rag_judge_prompt_template(prompt_file)
    user_content = template.format(
        question=question.strip(),
        reference_answer=(reference_answer or "").strip(),
        generated_answer=(generated_answer or "").strip(),
        judge_rule=(judge_rule or "").strip(),
        retrieved_evidence=(retrieved_evidence or "").strip(),
        generated_citations=(generated_citations or "").strip(),
        gold_doc_id=(gold_doc_id or "").strip(),
        gold_chunk_id=(gold_chunk_id or "").strip(),
    )
    client = create_deepseek_client()
    resp = client.chat.completions.create(
        model=model or config.DEEPSEEK_CHAT_MODEL or "deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": (
                    "Return one valid JSON object only. Do not use markdown. "
                    "Strictly follow the scoring rubric."
                ),
            },
            {"role": "user", "content": user_content},
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
    require_deepseek_chat_usage(usage, where="RAG multi-dimensional judge")

    payload = extract_json_object(raw)
    dimensions = [
        "answer_correctness",
        "answer_completeness",
        "citation_accuracy",
        "faithfulness",
    ]
    out: dict[str, Any] = {}
    scores: list[float] = []
    for key in dimensions:
        score, label, reason = _dimension_payload(payload, key)
        out[f"{key}_score"] = score
        out[f"{key}_label"] = label
        out[f"{key}_reason"] = reason
        scores.append(score)

    out["llm_judge_weighted_score"] = sum(scores) / len(scores) if scores else 0.0
    out["llm_judge_failure_type"] = str(
        payload.get("failure_type") or "none"
    ).strip()
    out["llm_judge_overall_reason"] = str(
        payload.get("overall_reason") or ""
    ).strip()
    out["llm_judge_total_tokens"] = usage.get("total_tokens", 0)
    return out
