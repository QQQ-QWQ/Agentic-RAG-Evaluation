"""
第三层研判（DeepSeek）：基于「用户目标 + 规划摘要 + 执行摘录」判断下一轮动作。

与 ``evaluation.ai_answer_judge``（评测打分）无关。
"""

from __future__ import annotations

from agentic_rag.deep_planning.session_planner import _extract_json_object
from agentic_rag.orchestration.types import JudgeVerdict, verdict_from_json


LAYER3_SYSTEM_PROMPT = """你是 Topic4【第三层：研判与调度】（Skill：质量与流程裁决，不解析用户原始输入中的路径/代码）。

【本层职能边界 — 你必须遵守】
- 你不重新从用户长文中抽取路径或代码；你基于「用户目标 + 第一层摘要 + 第二层执行摘录」（及可选的知识库对齐核验）判断本轮是否达标。
- 你不调用工具、不执行代码；只输出调度决策 JSON。

输入包含：用户目标、第一层规划摘要、第二层执行摘录（及可能的知识库对齐说明）。
你的职责 ONLY：
1. 判断当前执行是否已充分满足用户目标。
2. 决定下一步：**结束**、**让第二层在同规划下继续改进**、**返回第一层重新规划**、或**需要用户补充信息**。
3. 仅输出一个 JSON 对象，不要 Markdown 围栏。

JSON 字段：
- "verdict": 必须是下列之一字符串：
  - "complete" — 可以结束会话，答案可用。
  - "continue_execute" — 规划大体正确，但第二层输出需微调；给出 hint_for_next_execution。
  - "replan" — 规划或工具选型明显不对；给出 hint_for_next_planner。
  - "need_user_input" — 缺路径、歧义、违规模糊；在 summary_for_user 向用户说明要问什么。
- "summary_for_user": 给用户看的简短结论或追问（中文）。
- "hint_for_next_planner": 字符串或 null；verdict=replan 时填写。
- "hint_for_next_execution": 字符串或 null；verdict=continue_execute 时填写。
- "reasoning_brief": 一两句内部推理摘要（可展示给开发者）。
"""


def run_orchestration_judge(
    *,
    user_goal: str,
    plan_digest: str,
    execution_transcript: str,
    orchestration_round: int,
    temperature: float = 0.12,
    kb_grounding: dict | None = None,
) -> JudgeVerdict:
    """第三层单次调用。``kb_grounding`` 为 ``kb_grounding.run_kb_grounding_check`` 的结果（可选）。"""
    from langchain_core.messages import HumanMessage, SystemMessage

    from agentic_rag.deep_planning.agent_runner import build_deepseek_chat_model

    llm = build_deepseek_chat_model(temperature=temperature)
    kb_block = ""
    if kb_grounding and not kb_grounding.get("skipped"):
        kb_block = (
            "\n【知识库对齐核验（模型输出 vs 检索摘录）】\n"
            f"grounded={kb_grounding.get('grounded')} "
            f"confidence={kb_grounding.get('confidence')}\n"
            f"issues={kb_grounding.get('issues', '')}\n"
            "若 grounded=false 且任务声称来自文档，应倾向 replan 或 continue_execute。\n"
        )
    human = (
        f"编排轮次：{orchestration_round}\n\n"
        f"【用户目标】\n{user_goal.strip()}\n\n"
        f"【第一层规划摘要】\n{plan_digest.strip()}\n\n"
        f"{kb_block}"
        f"【第二层执行摘录】\n{execution_transcript.strip()[:12000]}\n"
    )
    msg = llm.invoke(
        [
            SystemMessage(content=LAYER3_SYSTEM_PROMPT),
            HumanMessage(content=human),
        ]
    )
    raw_text = msg.content if isinstance(msg.content, str) else str(msg.content)
    try:
        data = _extract_json_object(raw_text)
        return verdict_from_json(data)
    except Exception:
        return JudgeVerdict(
            verdict="complete",
            summary_for_user="（研判解析失败，默认结束本轮编排）",
            hint_for_next_planner=None,
            hint_for_next_execution=None,
            reasoning_brief="judge JSON parse fallback",
            raw={"error": True, "model_text": raw_text[:500]},
        )
