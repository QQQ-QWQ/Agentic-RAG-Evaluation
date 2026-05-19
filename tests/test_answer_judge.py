"""答案评判 mock API。"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from agentic_rag.evaluation.ai_answer_judge.judge import _normalize_score
from agentic_rag.evaluation.ai_answer_judge import (
    judge_answer_with_rule,
    judge_rag_response_with_rubric,
)


def test_normalize_score():
    assert _normalize_score(1) == 1.0
    assert _normalize_score(0.5) == 0.5
    assert _normalize_score(0) == 0.0


def test_judge_answer_with_rule_parses_json():
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock()]
    fake_resp.choices[0].message.content = (
        '{"score": 1, "label": "correct", "reason": "ok"}'
    )
    fake_usage = MagicMock()
    fake_usage.prompt_tokens = 10
    fake_usage.completion_tokens = 5
    fake_usage.total_tokens = 15
    fake_resp.usage = fake_usage

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_resp

    repo = Path(__file__).resolve().parents[1]
    with patch(
        "agentic_rag.evaluation.ai_answer_judge.judge.create_deepseek_client",
        return_value=fake_client,
    ):
        out = judge_answer_with_rule(
            question="q",
            reference_answer="r",
            generated_answer="a",
            judge_rule="rule",
            prompt_file=repo / "prompts" / "answer_judge_prompt.md",
        )

    assert out["correctness_score"] == 1.0
    assert out["judge_total_tokens"] == 15


def test_judge_rag_response_with_rubric_parses_json():
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock()]
    fake_resp.choices[0].message.content = (
        '{"answer_correctness":{"score":1,"reason":"ok"},'
        '"answer_completeness":{"score":0.5,"reason":"missing one point"},'
        '"citation_accuracy":{"score":0.5,"reason":"doc right chunk weak"},'
        '"faithfulness":{"score":1,"reason":"supported"},'
        '"failure_type":"weak_citation",'
        '"overall_reason":"mostly correct"}'
    )
    fake_usage = MagicMock()
    fake_usage.prompt_tokens = 20
    fake_usage.completion_tokens = 10
    fake_usage.total_tokens = 30
    fake_resp.usage = fake_usage

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_resp

    repo = Path(__file__).resolve().parents[1]
    with patch(
        "agentic_rag.evaluation.ai_answer_judge.judge.create_deepseek_client",
        return_value=fake_client,
    ):
        out = judge_rag_response_with_rubric(
            question="q",
            reference_answer="r",
            generated_answer="a",
            judge_rule="rule",
            retrieved_evidence="doc evidence",
            generated_citations="doc_001::chunk_0001",
            gold_doc_id="doc_001",
            gold_chunk_id="doc_001::chunk_0001",
            prompt_file=repo / "prompts" / "rag_multidim_judge_prompt.md",
        )

    assert out["answer_correctness_score"] == 1.0
    assert out["answer_completeness_score"] == 0.5
    assert out["citation_accuracy_score"] == 0.5
    assert out["faithfulness_score"] == 1.0
    assert out["llm_judge_failure_type"] == "weak_citation"
    assert out["llm_judge_total_tokens"] == 30
