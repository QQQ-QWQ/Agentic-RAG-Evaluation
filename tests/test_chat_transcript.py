from agentic_rag.telemetry.chat_transcript import (
    append_chat_turn,
    load_chat_turns,
    session_chat_log_path,
)


def test_append_and_load_chat_turns(tmp_path) -> None:
    sid = "abc123"
    p = session_chat_log_path(sid, project_root=tmp_path)
    assert "sessions/abc123/chat.jsonl" in p.as_posix().replace("\\", "/")
    append_chat_turn(
        sid,
        user_text="你好",
        assistant_text="你好，我是助手",
        project_root=tmp_path,
    )
    turns = load_chat_turns(sid, project_root=tmp_path)
    assert len(turns) == 1
    assert turns[0]["user"] == "你好"
    assert "助手" in turns[0]["assistant"]
