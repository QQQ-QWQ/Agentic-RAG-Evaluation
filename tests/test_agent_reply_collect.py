"""第二层答复文本合并（多段 AIMessage）。"""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agentic_rag.deep_planning.agent_runner import collect_ai_reply_text, format_agent_print


def test_collect_ai_reply_prefers_long_body_over_short_summary():
    long_body = "## Q001\n" + ("详细答案 " * 400)
    short_tail = "以上为全部 20 题的完整答案。"
    state = {
        "messages": [
            HumanMessage(content="questions"),
            AIMessage(content=long_body),
            ToolMessage(content="{}", tool_call_id="t1"),
            AIMessage(content=short_tail),
        ]
    }
    text = collect_ai_reply_text(state["messages"])
    assert "Q001" in text
    assert len(text) > 1500
    printed = format_agent_print(state)
    assert "Q001" in printed


def test_format_prior_conversation_from_log():
    from agentic_rag.orchestration.conversation_context import format_prior_conversation

    log = [
        {"role": "user", "content": "20 题 CSV"},
        {"role": "assistant", "content": "## Q001\n答案 A"},
    ]
    block = format_prior_conversation(log)
    assert "20 题" in block
    assert "Q001" in block
