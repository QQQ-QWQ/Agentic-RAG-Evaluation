"""答案评判 mock API。"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from agentic_rag.evaluation.ai_answer_judge.judge import _normalize_score
from agentic_rag.evaluation.ai_answer_judge import judge_answer_with_rule


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
