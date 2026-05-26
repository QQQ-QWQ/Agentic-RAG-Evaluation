from agentic_rag.orchestration.types import verdict_from_json
from agentic_rag.orchestration.judge_layer import CLAIM_LEVEL_SELF_CHECK_PROMPT


def test_verdict_mapping() -> None:
    v = verdict_from_json({"verdict": "replan", "summary_for_user": "ok"})
    assert v.verdict == "replan"
    assert v.summary_for_user == "ok"


def test_verdict_aliases() -> None:
    assert verdict_from_json({"verdict": "done"}).verdict == "complete"
    assert verdict_from_json({"verdict": "retry_execution"}).verdict == "continue_execute"


def test_verdict_parses_support_fields() -> None:
    v = verdict_from_json(
        {
            "verdict": "continue_execute",
            "support_verdict": "partially_supported",
            "unsupported_claims": ["claim a"],
            "missing_required_items": ["CRAG"],
            "citation_mismatches": ["claim a -> chunk_x"],
            "revision_instruction": "Add CRAG as insufficient evidence and replace chunk_x.",
        }
    )
    assert v.support_verdict == "partially_supported"
    assert v.unsupported_claims == ["claim a"]
    assert v.missing_required_items == ["CRAG"]
    assert v.citation_mismatches == ["claim a -> chunk_x"]
    assert v.revision_instruction == "Add CRAG as insufficient evidence and replace chunk_x."


def test_claim_level_prompt_requires_specific_revision_fields() -> None:
    assert "missing_required_items" in CLAIM_LEVEL_SELF_CHECK_PROMPT
    assert "citation_mismatches" in CLAIM_LEVEL_SELF_CHECK_PROMPT
    assert "revision_instruction" in CLAIM_LEVEL_SELF_CHECK_PROMPT


def test_claim_level_prompt_is_explicit() -> None:
    assert "Claim-Level Self-Check" in CLAIM_LEVEL_SELF_CHECK_PROMPT
    assert "3-5 条关键 claim" in CLAIM_LEVEL_SELF_CHECK_PROMPT
