"""日志查看：进行中会话检测与会话排序。"""

from __future__ import annotations

from agentic_rag.cli.logs_viewer import is_session_in_progress, list_session_ids
from agentic_rag.telemetry.session_trace import append_session_trace


def test_is_session_in_progress(tmp_path, monkeypatch):
    from agentic_rag import config

    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    sid = "sess_test_001"
    append_session_trace(sid, "session_start_gradio", {"ok": True})
    assert is_session_in_progress(sid) is False
    append_session_trace(sid, "client_turn_start", {"user_preview": "hi"})
    assert is_session_in_progress(sid) is True
    append_session_trace(sid, "client_turn_complete", {"stop_reason": "complete"})
    assert is_session_in_progress(sid) is False


def test_list_session_ids_by_mtime(tmp_path, monkeypatch):
    import time

    from agentic_rag import config

    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    append_session_trace("aaa_old", "session_start_gradio", {})
    time.sleep(0.05)
    append_session_trace("bbb_new", "session_start_gradio", {})
    ids = list_session_ids()
    assert ids[0] == "bbb_new"
