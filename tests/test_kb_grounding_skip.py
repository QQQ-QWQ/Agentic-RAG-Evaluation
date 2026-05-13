"""无 API：证据为空时 kb 核验直接跳过。"""

from agentic_rag.orchestration.kb_grounding import run_kb_grounding_check


def test_kb_grounding_skips_when_no_evidence() -> None:
    r = run_kb_grounding_check(
        question="q",
        generated_answer="a",
        evidence_excerpt="",
    )
    assert r["skipped"] is True
    assert r["grounded"] is False
