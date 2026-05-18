"""chat.jsonl 与 Gradio 恢复格式。"""

from __future__ import annotations

from agentic_rag.telemetry.chat_transcript import turns_to_gradio_messages


def test_turns_to_gradio_messages() -> None:
    turns = [
        {"user": "你好", "assistant": "您好"},
        {"user": "第二问", "assistant": ""},
    ]
    msgs = turns_to_gradio_messages(turns)
    assert msgs == [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "您好"},
        {"role": "user", "content": "第二问"},
    ]


def test_resume_client_command() -> None:
    from agentic_rag.cli.logs_viewer import resume_client_command

    cmd = resume_client_command("abc123", tier="c4")
    assert "--resume-session abc123" in cmd
    assert "client --c4" in cmd
