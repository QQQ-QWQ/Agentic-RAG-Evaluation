"""
Deep Agents 编排：使用 LangGraph 运行时 + Topic4 RAG 工具，实现动态规划循环。

依赖：``uv sync --group agent``（deepagents、langchain-openai）。

本模块在 import 时不拉取 langchain / deepagents，避免未安装 agent 组时污染默认环境。
"""

from __future__ import annotations

from typing import Any

from pathlib import Path

from agentic_rag import config


def _ensure_keys() -> None:
    if not config.DEEPSEEK_API_KEY:
        env_file = config.PROJECT_ROOT / ".env"
        hint = (
            f"请在 `{env_file}` 中配置 DEEPSEEK_API_KEY=…（或 OPENAI_API_KEY=…），"
            "并确认当前 shell 未 export 空的 DEEPSEEK_API_KEY。"
        )
        if not env_file.is_file():
            hint += " 若尚无文件，可复制 `.env.example` 为 `.env` 后填写。"
        raise ValueError(hint)
    if not config.ARK_API_KEY:
        raise ValueError(
            "请在 .env 中配置 ARK_API_KEY（RAG 嵌入仍走方舟）；"
            f"预期路径：`{config.PROJECT_ROOT / '.env'}`"
        )


def build_deepseek_chat_model(*, temperature: float = 0.35):
    """DeepSeek OpenAI 兼容接口；需模型支持 tool calling。"""
    from langchain_openai import ChatOpenAI

    _ensure_keys()
    return ChatOpenAI(
        model=config.DEEPSEEK_CHAT_MODEL or "deepseek-chat",
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_BASE_URL or "https://api.deepseek.com",
        temperature=temperature,
    )


DEFAULT_AGENT_SYSTEM_PROMPT = """\
你是 Topic4【第二层：执行与工具编排】（Skill：在真实环境中调用工具完成用户目标，不做「仅 JSON 规划」）。

【本层职能边界 — 你必须遵守】
- 第一层已给出规划摘要与用户原文要点；你负责落实：用工具完成检索、入库、（可选）沙箱跑代码。你不替代第一层重复输出完整 JSON 规划，但若发现路径/任务理解明显错误，可在答复中说明并仍按可用工具尽力执行。
- 「解析」职责：从用户原文与第一层 plan_for_layer2 中识别：要问什么问题（写入 topic4_rag_query 的 question）、是否需要把某工程内文件入库（topic4_kb_ingest）、是否需先把 Office/PDF 等转成 Markdown 再推理（topic4_file_to_markdown）、是否要验证代码片段（sandbox_exec_python）。路径必须落在工程根目录内方可入库或转 Markdown。
- 所有可执行动作仅通过下列工具完成；不要假装已执行。

默认检索范围：工程 Chroma「全库知识库」（data/processed/documents.csv）；若系统提示已绑定单文件，则该文件范围优先。

可用工具：
- topic4_list_rag_pipelines：列出管线名称。
- topic4_rag_query：向知识库或绑定文档提问；pipeline 选管线 id。
- topic4_kb_ingest：工程内文件登记入全库并重建索引。
- topic4_file_to_markdown：用 Microsoft MarkItDown 将工程内 PDF/Office/HTML 等转为 Markdown 文本（路径须在工程根内；大文件有字节上限）。
- sandbox_exec_python（若已启用）：隔离目录执行 Python，验证代码。

执行要求：
1. 可配合 write_todos 拆解步骤。
2. 检索可先轻后重（如 c0_naive → c2_stage3_context），并在最终答复说明使用的管线。
3. 禁止编造工具未返回的引用或片段。
4. 最终中文答复简洁可读。
5. 验证代码优先 sandbox_exec_python；勿在主机任意执行未授权 shell。
"""


def build_topic4_deep_agent(
    doc_path: str | Path | None = None,
    *,
    use_knowledge_base: bool | None = None,
    system_prompt: str | None = None,
    temperature: float = 0.35,
    sandbox_workspace: Path | None = None,
    additional_tools: list[Any] | None = None,
):
    """创建 Deep Agent（内置 todos / 虚拟文件系统等 + Topic4 RAG 工具；可选沙箱）。

    ``use_knowledge_base`` 未指定时：``doc_path is None`` → Chroma 全库，否则单文档。
    显式 ``use_knowledge_base=False`` 时必须提供 ``doc_path``。

    ``additional_tools``：由编排钩子 ``OrchestrationHooks.extend_agent_tools`` 等在运行时追加的
    LangChain 工具列表（与内置 Topic4 工具合并）。
    """
    from deepagents import create_deep_agent

    from agentic_rag.deep_planning.tools_factory import build_topic4_rag_tools

    resolved_kb = doc_path is None if use_knowledge_base is None else use_knowledge_base
    if not resolved_kb and doc_path is None:
        raise ValueError("单文档检索模式必须提供 doc_path")

    model = build_deepseek_chat_model(temperature=temperature)
    tools = build_topic4_rag_tools(
        doc_path,
        use_knowledge_base=resolved_kb,
        sandbox_workspace=sandbox_workspace,
    )
    if additional_tools:
        tools = [*tools, *additional_tools]
    base = system_prompt or DEFAULT_AGENT_SYSTEM_PROMPT
    if resolved_kb:
        sys_msg = (
            base
            + "\n\n【本会话检索范围】工程 Chroma 全库知识库（默认；与批量实验共用索引）。"
        )
    else:
        assert doc_path is not None, "单文档模式必须提供 doc_path"
        bound = Path(doc_path).expanduser().resolve()
        sys_msg = base + f"\n\n【本会话绑定文档（只读）】\n{bound}"
    if sandbox_workspace is not None and not config.SANDBOX_ENABLED:
        sys_msg += (
            "\n\n【提示】已传入沙箱工作目录，但 SANDBOX_ENABLED 未为 true，"
            "sandbox_exec_python 未注册；可在 .env 中开启。"
        )
    elif sandbox_workspace is not None and config.SANDBOX_ENABLED:
        sys_msg += f"\n\n【沙箱工作目录】\n{sandbox_workspace.resolve()}"
    return create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=sys_msg,
    )


def last_ai_text(messages: list[Any]) -> str:
    """从消息列表中取最后一条 AI 文本。"""
    from langchain_core.messages import AIMessage

    for m in reversed(messages):
        if isinstance(m, AIMessage):
            c = m.content
            if isinstance(c, str):
                return c
            if isinstance(c, list):
                parts = []
                for block in c:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        parts.append(block)
                return "\n".join(parts)
    return ""


def invoke_agent_once(
    agent,
    user_text: str,
) -> dict[str, Any]:
    """单次 invoke，返回完整 state（含 messages）。"""
    from langchain_core.messages import HumanMessage

    out = agent.invoke({"messages": [HumanMessage(content=user_text.strip())]})
    return out if isinstance(out, dict) else {"result": out}


def format_agent_print(final_state: dict[str, Any]) -> str:
    """终端打印友好输出。"""
    msgs = final_state.get("messages") or []
    if not isinstance(msgs, list):
        return str(final_state)
    text = last_ai_text(msgs)
    return text if text.strip() else repr(final_state)
