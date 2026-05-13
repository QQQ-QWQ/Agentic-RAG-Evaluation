from agentic_rag.orchestration.types import verdict_from_json


def test_verdict_mapping() -> None:
    v = verdict_from_json({"verdict": "replan", "summary_for_user": "ok"})
    assert v.verdict == "replan"
    assert v.summary_for_user == "ok"


def test_verdict_aliases() -> None:
    assert verdict_from_json({"verdict": "done"}).verdict == "complete"
    assert verdict_from_json({"verdict": "retry_execution"}).verdict == "continue_execute"
