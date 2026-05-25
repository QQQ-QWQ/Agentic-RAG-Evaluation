"""JSON 解析与研判容错。"""

from agentic_rag.deep_planning.session_planner import _extract_json_object
from agentic_rag.orchestration.types import verdict_from_json


def test_extract_json_object_from_array():
    raw = '[{"verdict": "complete", "summary_for_user": "ok"}]'
    data = _extract_json_object(raw)
    assert data["verdict"] == "complete"


def test_verdict_from_json_list():
    v = verdict_from_json([{"verdict": "replan", "summary_for_user": "x"}])
    assert v.verdict == "replan"
