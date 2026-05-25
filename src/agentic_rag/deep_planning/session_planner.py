"""
第一层编排（DeepSeek）：**结构化解析与填槽**（路径候选、任务摘要、管线建议），
不执行代码、不调工具、不跑 RAG；混合输入由模型在 JSON 中消化。

第二层负责 **工具执行**（检索 / 入库 / MarkItDown 读文件转 Markdown / 沙箱代码执行）；第三层负责 **达标与否与调度**。

与评测用的 ``evaluation.ai_answer_judge`` 无关。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


LAYER1_SYSTEM_PROMPT = """你是 Topic4 多层级编排中的【第一层：会话规划模型】（Skill：结构化解析与路由，不执行）。

【本层职能边界 — 你必须遵守】
- 你是「解析器 + 填槽器」：接收用户一整段原始输入（可为混合内容），把信息填入下方 JSON 字段；你不调用工具、不运行代码、不执行终端命令、不做向量检索。
- 用户输入可能包含：纯自然语言、夹杂的路径（Windows/Linux，含引号或反斜杠）、粘贴的 CSV/表格行、对代码片段的文字描述等。你的任务是理解意图并把「路径候选」「任务焦点」分离进 JSON，不必在用户可见回复里重复粘贴全文。
- 第二层工具分档位：**C3** 仅 ``topic4_list_rag_pipelines``、``topic4_rag_query``。**C4** 另可 Firecrawl、``topic4_file_read`` / ``topic4_file_write`` / ``topic4_file_edit`` / ``topic4_file_ingest``、``topic4_shell_exec``、计算器/表格/沙箱等。消息中会标明【当前档位 C3 或 C4】；若为 C3，禁止在 plan 中安排 Firecrawl 或本地文件工具。
- **是否需要网页抓取/搜索**（仅 C4 有效）：needs_web_tools=true 表示用户依赖 http(s) 网页；请把识别到的链接写入 web_urls 数组。Firecrawl **不能**访问用户电脑上的文件。
- **本地文件**：从原文抽取的路径写入 local_paths；C4 第二层按需 topic4_file_read / write / edit / ingest；系统命令用 topic4_shell_exec。
- 路径抽取规则：仅当你能识别出指向真实文件的合法路径字符串时填入 document_path；否则 null（表示默认使用工程内 Chroma 全库知识库，而非单文件）。不要把 CSV 里的逗号分隔字段误当成路径，除非某字段明确是路径。
- **是否要从知识库检索**：由 needs_retrieval_tools 表达；false 表示第二层不要为「答题」去调 topic4_rag_query（仍可按 plan_for_layer2 做入库、沙箱等）。
- **入库意图**（仅声明，第二层执行）：kb_mutation_intent 取 none | ingest_if_missing | ingest_force。
  - none：未要求把新文件写入知识库清单；
  - ingest_if_missing：若系统稍后提示该路径「未在 documents.csv 登记」，再调 topic4_file_ingest；已登记则不必为「已在库」而再入库；
  - ingest_force：用户明确要求更新/重新登记该文件时再调 topic4_file_ingest（仍会重建索引，慎用）。

【职责 ONLY】
1. 判断用户核心任务与是否需要检索增强（RAG 工具链，见 needs_retrieval_tools）。
2. 尽力从文本中抽取单文档路径候选；抽不出则 null。
3. 判断用户是否希望写入/更新知识库清单（kb_mutation_intent），与是否需要检索相互独立。
4. 产出第二层可执行的简短规划（plan_for_layer2）与管线建议（suggested_pipelines）。

硬性规则：
- 仅输出一个 JSON 对象，不要 Markdown 围栏，不要多余解释。
- 若用户在命令行已提供文档路径（消息中会写【命令行已绑定文档】），将该路径写入 document_from_cli；document_path 可与之一致或留由用户文本覆盖（以命令行为准时已在系统侧处理）。
- 用户未给出可用单文件路径且命令行也未绑文档时，document_path / document_from_cli 可为 null，表示全库检索。

JSON 字段说明：
- "document_path": string | null   // 从用户原文抽取的路径；无法确定则为 null
- "document_from_cli": string | null // 若消息中给出命令行绑定路径则照抄，否则 null
- "task_summary": string           // 用户想达成什么（精炼，不必复述粘贴全文）
- "needs_retrieval_tools": boolean // 是否需要调用 topic4_rag_query 从知识库/绑定文档检索证据
- "needs_web_tools": boolean      // 仅 C4：是否需 Firecrawl 抓取/搜索网页
- "web_urls": string[]            // 从用户原文识别的 http(s) 链接（可空数组）
- "local_paths": string[]         // 从用户原文识别的本地文件路径候选（可空数组）
- "kb_mutation_intent": "none" | "ingest_if_missing" | "ingest_force"  // 见上文规则
- "suggested_pipelines": string[]  // 可选，如 ["c0_naive"]、["c2_stage3_context"]，不确定可为 []
- "plan_for_layer2": string       // 给第二层的执行提示：检索 / 入库 / 验证代码等由谁做（第二层用工具完成）
- "reasoning_brief": string       // 给用户看的一两句说明
"""


@dataclass
class SessionPlan:
    """第一层规划结果（结构化）。"""

    document_path: str | None
    task_summary: str
    needs_retrieval_tools: bool
    suggested_pipelines: list[str]
    plan_for_layer2: str
    reasoning_brief: str
    raw: dict[str, Any]
    kb_mutation_intent: str = "none"
    needs_web_tools: bool = False
    web_urls: list[str] = field(default_factory=list)
    local_paths: list[str] = field(default_factory=list)


def _extract_json_object(text: str) -> dict[str, Any]:
    """从模型输出中抠出 JSON object。"""
    t = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", t)
    if fence:
        t = fence.group(1).strip()
    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"输出中无 JSON 对象：{text[:200]}…")
    parsed = json.loads(t[start : end + 1])
    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, dict):
                return item
    raise ValueError(f"JSON 解析结果不是 object：{type(parsed).__name__}")


def looks_like_document_path(value: str | None) -> bool:
    """过滤 UI 检索范围文案等误填进 document_path 的非路径字符串。"""
    if not value or not str(value).strip():
        return False
    s = str(value).strip()
    if "\n" in s or len(s) > 260:
        return False
    if s.startswith("检索范围") or "检索范围" in s[:48]:
        return False
    if "**" in s and "/" not in s and "\\" not in s:
        return False
    if re.match(r"^[A-Za-z]:[/\\]", s):
        return True
    if s.startswith(("/", "./", "../", "~")):
        return True
    if ("/" in s or "\\" in s) and re.search(
        r"\.(md|pdf|csv|txt|jsonl|py|yaml|yml|docx|xlsx)\b", s, re.I
    ):
        return True
    try:
        return Path(s).expanduser().is_file()
    except OSError:
        return False


def _coerce_document_path(value: str | None) -> str | None:
    if not value or not str(value).strip():
        return None
    s = str(value).strip().strip('"')
    if looks_like_document_path(s):
        return s
    return None


def _merge_str_lists(*parts: list[str] | None) -> list[str]:
    out: list[str] = []
    for part in parts:
        if not part:
            continue
        for u in part:
            s = (u or "").strip()
            if s and s not in out:
                out.append(s)
    return out


def format_c4_parsed_input_block(plan: SessionPlan) -> str:
    """C4：系统侧从用户原文预解析的链接与本地路径（供第二层优先调用工具）。"""
    lines: list[str] = []
    if plan.web_urls:
        lines.append("【系统从用户原文解析到的 http(s) 链接 — 请用 topic4_firecrawl_scrape 逐条抓取】")
        for u in plan.web_urls[:12]:
            lines.append(f"- {u}")
        if len(plan.web_urls) > 12:
            lines.append(f"- … 另有 {len(plan.web_urls) - 12} 条")
    if plan.local_paths:
        from agentic_rag import config as app_config
        from agentic_rag.documents.multi_doc import resolve_document_paths

        root = app_config.PROJECT_ROOT.resolve()
        resolved, errs = resolve_document_paths(plan.local_paths, project_root=root)
        resolved_set = {str(r) for r in resolved}
        lines.append(
            "【系统从用户原文解析到的本地文件路径 — 请按需调用 topic4_file_read；"
            "需入库时用 topic4_file_ingest；Firecrawl 不能读本地文件】"
        )
        for token in plan.local_paths[:10]:
            t = (token or "").strip()
            p = Path(t).expanduser()
            if not p.is_absolute():
                p = (root / p).resolve()
            else:
                p = p.resolve()
            flag = "存在" if (str(p) in resolved_set or p.is_file()) else "未找到"
            lines.append(f"- {t} （{flag}）")
        for e in errs[:3]:
            lines.append(f"- 解析提示：{e}")
    if not lines:
        return ""
    return "\n".join(lines) + "\n\n"


def run_layer1_session_plan(
    user_natural_language: str,
    *,
    cli_document_path: str | None = None,
    prior_context: str | None = None,
    temperature: float = 0.15,
    planning_preamble: str | None = None,
    enable_c4_tools: bool = False,
) -> SessionPlan:
    """
    第一层：单次模型调用，返回结构化规划。

    Parameters
    ----------
    user_natural_language
        用户一段自然语言（可同时包含路径与任务）。
    cli_document_path
        若用户在 ``main.py agent <路径>`` 已指定，传入以便第一层写入 document_from_cli。
    prior_context
        前几轮编排、研判层给出的摘要；重规划时传入以便第一层连贯决策。
    planning_preamble
        置于「用户自然语言输入」之前的附加块（如查询改写、自定义 enricher），由编排器组装。
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    from agentic_rag.deep_planning.agent_runner import build_deepseek_chat_model

    llm = build_deepseek_chat_model(temperature=temperature)
    hint = ""
    cli_path = _coerce_document_path(cli_document_path)
    if cli_path:
        hint = f"\n【命令行已绑定文档】{cli_path}\n"
    prior = ""
    if prior_context and prior_context.strip():
        prior = f"\n【编排上下文·供重规划参考】\n{prior_context.strip()}\n"

    tier = "C4 Tool-Augmented" if enable_c4_tools else "C3 Agentic Retrieval"
    blocks: list[str] = [
        f"【当前档位】{tier}（C3 无 Firecrawl/读本地文件工具；C4 可有）",
    ]
    if planning_preamble and planning_preamble.strip():
        blocks.append(planning_preamble.strip())
    if hint.strip():
        blocks.append(hint.strip())
    if prior.strip():
        blocks.append(prior.strip())
    blocks.append("【用户自然语言输入】\n" + user_natural_language.strip() + "\n")
    human = "\n\n".join(blocks)

    try:
        msg = llm.invoke(
            [
                SystemMessage(content=LAYER1_SYSTEM_PROMPT),
                HumanMessage(content=human),
            ]
        )
    except Exception as exc:
        try:
            from agentic_rag.telemetry.audit_log import audit_record, get_audit_session_id

            audit_record(
                "layer1_plan_error",
                session_id=get_audit_session_id(),
                payload={"error_type": type(exc).__name__, "error": str(exc)[:2000]},
            )
        except Exception:
            pass
        raise RuntimeError(
            f"第一层规划调用 DeepSeek 失败（{type(exc).__name__}）：{exc}"
        ) from exc

    raw_text = msg.content if isinstance(msg.content, str) else str(msg.content)
    data = _extract_json_object(raw_text)

    doc_raw = data.get("document_path")
    doc_cli = data.get("document_from_cli")
    path_candidate = None
    if cli_path:
        path_candidate = cli_path
    elif isinstance(doc_cli, str) and doc_cli.strip():
        path_candidate = _coerce_document_path(doc_cli.strip().strip('"'))
    elif isinstance(doc_raw, str) and doc_raw.strip():
        path_candidate = _coerce_document_path(doc_raw.strip().strip('"'))

    pipelines = data.get("suggested_pipelines") or []
    if not isinstance(pipelines, list):
        pipelines = []

    kb_raw = str(data.get("kb_mutation_intent") or "none").strip().lower()
    if kb_raw not in ("none", "ingest_if_missing", "ingest_force"):
        kb_raw = "none"

    from agentic_rag.documents.multi_doc import parse_document_paths_from_text
    from agentic_rag.tools.firecrawl_tool import extract_http_urls_from_text

    det_urls = extract_http_urls_from_text(user_natural_language)
    model_urls = data.get("web_urls") if isinstance(data.get("web_urls"), list) else []
    web_urls = _merge_str_lists(det_urls, [str(x) for x in model_urls])

    det_paths = parse_document_paths_from_text(user_natural_language)
    model_paths = data.get("local_paths") if isinstance(data.get("local_paths"), list) else []
    local_paths = _merge_str_lists(det_paths, [str(x) for x in model_paths])

    needs_web = bool(data.get("needs_web_tools", False))
    if enable_c4_tools and web_urls and not needs_web:
        needs_web = True

    return SessionPlan(
        document_path=path_candidate,
        task_summary=str(data.get("task_summary") or "").strip() or "(未摘要)",
        needs_retrieval_tools=bool(data.get("needs_retrieval_tools", True)),
        needs_web_tools=needs_web if enable_c4_tools else False,
        web_urls=web_urls if enable_c4_tools else [],
        local_paths=local_paths if enable_c4_tools else [],
        suggested_pipelines=[str(x) for x in pipelines],
        plan_for_layer2=str(data.get("plan_for_layer2") or "").strip(),
        reasoning_brief=str(data.get("reasoning_brief") or "").strip(),
        raw=data,
        kb_mutation_intent=kb_raw,
    )


def resolve_document_path(plan: SessionPlan) -> Path | None:
    """将第一层给出的路径解析为 Path；不存在则返回 None。"""
    if not plan.document_path or not looks_like_document_path(plan.document_path):
        return None
    p = Path(plan.document_path).expanduser().resolve()
    if p.is_file():
        return p
    return None


def compose_layer2_user_message(
    *,
    user_original: str,
    plan: SessionPlan,
    orchestration_addon: str | None = None,
    retrieval_scope_note: str | None = None,
    use_knowledge_base: bool = True,
    kb_execution_notes: str | None = None,
    enable_c4_tools: bool = True,
) -> str:
    """拼第二层 HumanMessage：嵌入第一层规划；可选附加编排系统备注（研判重试等）。"""
    pipes = ", ".join(plan.suggested_pipelines) if plan.suggested_pipelines else "(由你自选)"
    addon = ""
    if orchestration_addon and orchestration_addon.strip():
        addon = (
            "\n【编排系统备注（第三层或调度器注入，请一并执行）】\n"
            f"{orchestration_addon.strip()}\n"
        )
    scope_block = ""
    if retrieval_scope_note and str(retrieval_scope_note).strip():
        scope_block = (
            "\n【系统侧·检索范围（说明文字，不是文件路径）】\n"
            f"{str(retrieval_scope_note).strip()}\n"
        )
    scope_hint = (
        "请基于工程 Chroma 全库知识库检索结果作答，"
        if use_knowledge_base
        else "请严格基于已绑定单文档的检索结果作答，"
    )
    from agentic_rag.tools.firecrawl_tool import firecrawl_configured

    parsed_block = format_c4_parsed_input_block(plan) if enable_c4_tools else ""
    web_line = ""
    if enable_c4_tools and (plan.needs_web_tools or plan.web_urls):
        if firecrawl_configured():
            web_line = (
                "用户问题涉及网页：请对【系统解析到的链接】或 plan 中的 URL 调用 "
                "topic4_firecrawl_scrape（每条链接一次）；无 URL 时可 topic4_firecrawl_search。"
                "输出 JSON 含 schema_version=topic4.tool.v1。\n"
            )
        else:
            web_line = (
                "第一层要求网页能力，但 **FIRECRAWL_API_KEY 未配置**。"
                "禁止用 topic4_shell_exec / curl 代替 Firecrawl；"
                "请基于知识库已有内容作答，并说明当前环境无法联网抓取。\n"
            )
    if enable_c4_tools:
        tool_hint = (
            "按需调用 topic4_list_rag_pipelines / topic4_rag_query；"
            if plan.needs_retrieval_tools
            else "第一层已标记 needs_retrieval_tools=false：不要仅为「答题」去调用 topic4_rag_query；"
            "若 plan_for_layer2 仍要求检索则除外。"
        )
        kb_tool_line = (
            "本地路径用 topic4_file_read；入库用 topic4_file_ingest；"
            "网页入库用 topic4_firecrawl_scrape_to_kb。\n"
        )
    else:
        tool_hint = (
            "【C3 模式】仅 topic4_list_rag_pipelines / topic4_rag_query；"
            "禁止 Firecrawl、读本地文件、入库、MarkItDown、沙箱。"
            if plan.needs_retrieval_tools
            else "第一层已标记 needs_retrieval_tools=false：不要仅为「答题」去调用 topic4_rag_query。"
        )
        kb_tool_line = ""
        parsed_block = ""
        web_line = ""
    return (
        "【第二层接入 · 第一层规划结果】\n"
        f"- 任务摘要：{plan.task_summary}\n"
        f"- 是否需要检索工具（topic4_rag_query）：{plan.needs_retrieval_tools}\n"
        f"- 是否需要网页工具（Firecrawl，仅 C4）：{plan.needs_web_tools}\n"
        f"- 入库意图 kb_mutation_intent：{plan.kb_mutation_intent}\n"
        f"- 建议管线（可参考）：{pipes}\n"
        f"- 给执行层的提示：{plan.plan_for_layer2 or '按任务摘要调用 Topic4 工具完成'}\n"
        f"- 第一层说明：{plan.reasoning_brief or '无'}\n"
        f"{addon}"
        f"{scope_block}"
        "【用户原文】\n"
        f"{user_original.strip()}\n\n"
        f"{parsed_block}"
        f"{scope_hint}"
        f"{tool_hint}\n"
        f"{web_line}"
        f"{kb_tool_line}"
        + (
            f"\n【系统侧·知识库与入库（以 documents.csv 为准）】\n{kb_execution_notes.strip()}\n"
            if kb_execution_notes and kb_execution_notes.strip()
            else ""
        )
    )


def format_layer1_console(plan: SessionPlan) -> str:
    """终端展示第一层思考（简短）。"""
    path_line = plan.document_path or "（未指定单文件 → 默认使用工程 Chroma 全库知识库）"
    lines = [
        "--- 第一层（会话规划）---",
        f"任务摘要：{plan.task_summary}",
        f"是否依赖检索工具：{plan.needs_retrieval_tools}",
        f"是否依赖网页工具（Firecrawl，仅 C4）：{plan.needs_web_tools}",
        f"入库意图 kb_mutation_intent：{plan.kb_mutation_intent}",
        f"路径判定：{path_line}",
        f"解析到的网页链接：{', '.join(plan.web_urls[:5]) or '（无）'}"
        + (f" …共{len(plan.web_urls)}条" if len(plan.web_urls) > 5 else ""),
        f"解析到的本地路径：{', '.join(plan.local_paths[:3]) or '（无）'}"
        + (f" …共{len(plan.local_paths)}条" if len(plan.local_paths) > 3 else ""),
        f"说明：{plan.reasoning_brief}",
        "--- 随后：第二层执行 → 第三层研判（可重规划 / 继续执行）---",
    ]
    return "\n".join(lines)
