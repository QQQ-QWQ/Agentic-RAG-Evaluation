"""
将 ``run_document_rag`` 封装为 LangChain Tool；可选注册本地 Python 沙箱工具。

仅在安装 ``dependency-groups.agent`` 后使用。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from agentic_rag import config as app_config
from agentic_rag.deep_planning.presets import describe_presets, list_preset_ids, run_profile_for_preset
from agentic_rag.experiment.kb_ingest import ingest_local_file_to_kb
from agentic_rag.experiment.runner import run_document_rag, run_knowledge_base_rag
from agentic_rag.tools.file_tool import (
    format_file_ingest_response,
    format_file_read_response,
    ingest_file_to_kb,
    read_file_content,
)
from agentic_rag.tools.firecrawl_tool import (
    firecrawl_configured,
    format_scrape_tool_response,
    format_search_tool_response,
    scrape_to_markdown_file,
    scrape_url,
    search_web,
)
from agentic_rag.tools.response_format import tool_response_json


def _retrieved_doc_ids(raw: dict[str, Any]) -> list[str]:
    seen: list[str] = []
    for ch in raw.get("retrieved_chunks") or []:
        if not isinstance(ch, dict):
            continue
        did = str(ch.get("doc_id") or "").strip()
        if did and did not in seen:
            seen.append(did)
    return seen


def _chunks_to_evidence_excerpt(raw: dict[str, Any], *, max_chars: int) -> str:
    chunks = raw.get("retrieved_chunks") or []
    parts: list[str] = []
    for i, ch in enumerate(chunks[:12]):
        if isinstance(ch, dict):
            t = (ch.get("text") or "").strip()
            cid = ch.get("chunk_id", "")
            did = ch.get("doc_id", "")
            parts.append(f"[{i + 1} doc_id={did} chunk_id={cid}]\n{t}")
    s = "\n\n".join(parts)
    return s[:max_chars]


def _compact_rag_result(
    raw: dict[str, Any],
    *,
    pipeline: str,
    max_chars: int = 14_000,
    evidence_max_chars: int = 8000,
) -> str:
    """压缩传给模型的工具输出；附带 evidence_excerpt 供对齐核验。"""
    slim: dict[str, Any] = {
        "pipeline": pipeline,
        "config_flag": raw.get("config") or raw.get("run_profile", {}).get("config_name"),
        "allowed_doc_ids": raw.get("allowed_doc_ids"),
        "retrieved_doc_ids": _retrieved_doc_ids(raw),
        "answer": raw.get("answer", ""),
        "error": raw.get("error", ""),
        "latency_ms": raw.get("latency_ms"),
        "citations": raw.get("citations"),
        "original_query": raw.get("original_query"),
        "rewritten_query": raw.get("rewritten_query"),
        "evidence_excerpt": _chunks_to_evidence_excerpt(raw, max_chars=evidence_max_chars),
    }
    text = json.dumps(slim, ensure_ascii=False, indent=2)
    if len(text) > max_chars:
        text = text[: max_chars - 20] + "\n…(truncated)"
    return text


def _sandbox_python_tool(workspace: Path):
    root = Path(workspace).resolve()

    @tool
    def sandbox_exec_python(code: str) -> str:
        """在隔离工作目录中执行 Python 源码（验证算法、跑简短自检）。

        需环境变量 ``SANDBOX_ENABLED=true``；超时见 ``SANDBOX_TIMEOUT_SEC``。
        cwd 固定为会话临时目录；勿执行不可信代码。
        """
        from agentic_rag.sandbox.local_subprocess import exec_python_snippet

        try:
            result = exec_python_snippet(root, code)
            return result.format_cli()
        except subprocess.TimeoutExpired as e:
            return json.dumps({"error": "timeout", "detail": str(e)}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": type(e).__name__, "detail": str(e)}, ensure_ascii=False)

    return sandbox_exec_python


def _build_firecrawl_tools(*, enable_c4_tools: bool) -> list[Any]:
    """Firecrawl 仅 C4；需 FIRECRAWL_API_KEY。返回统一 schema_version=topic4.tool.v1 的 JSON。"""
    if not enable_c4_tools or not firecrawl_configured():
        return []

    @tool
    def topic4_firecrawl_scrape(url: str, max_output_chars: int = 80_000) -> str:
        """【C4 · 网页】抓取 http(s) URL → Markdown。

        当用户原文含链接、或 plan 要求读在线文档时调用。Firecrawl **不能**读取本地磁盘文件。
        本地文件用 topic4_file_read。知识库已有内容时优先 topic4_rag_query。
        """
        res = scrape_url(url, max_output_chars=max_output_chars)
        return format_scrape_tool_response(res)

    @tool
    def topic4_firecrawl_search(
        query: str,
        limit: int = 5,
        max_output_chars: int = 80_000,
    ) -> str:
        """【C4 · 网页】搜索互联网；返回 items[].url/title/description。

        用户未给具体 URL 但需查在线资料时使用；拿到 URL 后再 topic4_firecrawl_scrape。
        """
        res = search_web(query, limit=limit, max_output_chars=max_output_chars)
        return format_search_tool_response(res)

    @tool
    def topic4_firecrawl_scrape_to_kb(url: str, title: str = "") -> str:
        """【C4 · 网页入库】抓取 URL → data/raw/web_snapshots/ → documents.csv + 重建 Chroma。

        仅当用户要求把网页纳入知识库时使用。
        """
        root = Path(app_config.PROJECT_ROOT).resolve()
        saved, snap = scrape_to_markdown_file(
            url,
            project_root=root,
            title=title.strip() or None,
        )
        if not saved:
            return tool_response_json(
                "topic4_firecrawl_scrape_to_kb",
                ok=False,
                data=snap,
                error=str(snap.get("error") or "抓取或保存失败"),
            )
        ingest = ingest_local_file_to_kb(
            root,
            saved,
            title=title.strip() or snap.get("relative_path", ""),
            source_note=f"Firecrawl 抓取入库: {snap.get('url', url)}",
        )
        ok = bool(ingest.get("ok"))
        return tool_response_json(
            "topic4_firecrawl_scrape_to_kb",
            ok=ok,
            data={"snapshot": snap, "ingest": ingest},
            error=None if ok else str(ingest.get("error") or "入库失败"),
            hints=["入库后可用 topic4_rag_query 检索该页内容。"] if ok else [],
        )

    return [
        topic4_firecrawl_scrape,
        topic4_firecrawl_search,
        topic4_firecrawl_scrape_to_kb,
    ]


def _build_c4_file_tools(*, enable_c4_tools: bool) -> list[Any]:
    """C4 本地文件工具族（与 Firecrawl 对称）：动态读盘 + 入库。"""
    if not enable_c4_tools:
        return []

    @tool
    def topic4_file_read(file_path: str, max_output_chars: int = 120_000) -> str:
        """【C4 · 本地文件 · 读取】读取用户给出的磁盘路径（PDF/DOCX/MD 等），**不是** Firecrawl。

        当用户原文含本地路径、或第一层 local_paths / plan 要求读文件时调用。
        工程根内用 MarkItDown；根外只读 parse_path。要纳入 Chroma 请改调 topic4_file_ingest。
        返回 JSON schema_version=topic4.tool.v1，正文在 data.text。
        """
        root = Path(app_config.PROJECT_ROOT).resolve()
        res = read_file_content(
            file_path,
            project_root=root,
            max_output_chars=max_output_chars,
        )
        return format_file_read_response(res)

    @tool
    def topic4_file_ingest(file_path: str, title: str = "") -> str:
        """【C4 · 系统库入库】仅用于 **系统知识库** 维护，会写入 documents.csv 并重建 Chroma。

        用户会话附加文件请通过客户端「会话路径」绑定（临时索引，不调本工具）。
        批量维护系统库请用 ``main.py kb sync`` / ``kb reset``。
        """
        root = Path(app_config.PROJECT_ROOT).resolve()
        from agentic_rag.experiment.kb_paths import is_excluded_from_system_sync

        raw = (file_path or "").strip().strip('"').strip("'")
        fp = Path(raw).expanduser()
        if not fp.is_absolute():
            fp = (root / fp).resolve()
        else:
            fp = fp.resolve()
        try:
            rel = fp.relative_to(root).as_posix()
        except ValueError:
            rel = ""
        if not rel or is_excluded_from_system_sync(rel):
            return format_file_ingest_response(
                {
                    "ok": False,
                    "error": (
                        "该路径属于会话附加区或工程外文件，不会写入系统全库。"
                        "请在客户端开始会话时填写路径（临时索引），"
                        "或将文件放入 data/raw 下系统目录后执行 main.py kb sync。"
                    ),
                }
            )
        from agentic_rag.experiment.kb_ingest import ingest_local_file_to_kb

        report = ingest_local_file_to_kb(
            root,
            fp,
            title=title.strip() or None,
            source_note="topic4_file_ingest 单文件入库",
            copy_file=False,
        )
        return format_file_ingest_response(report)

    return [topic4_file_read, topic4_file_ingest]


def build_topic4_rag_tools(
    doc_path: str | Path | None = None,
    *,
    use_knowledge_base: bool | None = None,
    kb_doc_ids: list[str] | None = None,
    sandbox_workspace: Path | None = None,
    enable_c4_tools: bool = True,
) -> list[Any]:
    """
    - C3（``enable_c4_tools=False``）：仅 ``topic4_list_rag_pipelines`` + ``topic4_rag_query``（无 Firecrawl / 本地读盘）。
    - C4（``enable_c4_tools=True``）：Firecrawl 三件套、``topic4_file_read`` / ``topic4_file_ingest``、可选沙箱。

    ``use_knowledge_base`` 未指定时：``doc_path is None`` → Chroma 全库，否则单文档。
    """
    use_kb = doc_path is None if use_knowledge_base is None else use_knowledge_base
    if not use_kb and doc_path is None:
        raise ValueError("单文档模式下必须提供 doc_path")

    path_str: str | None = None
    if not use_kb:
        path_str = str(Path(doc_path).expanduser().resolve())

    @tool
    def topic4_list_rag_pipelines() -> str:
        """列出 Topic4 可用的 RAG 管线名称（pipeline）及含义；规划选型前先调用。"""
        return describe_presets()

    @tool
    def topic4_rag_query(question: str, pipeline: str = "project_default") -> str:
        """对知识库或绑定文档执行 RAG 问答（默认工程 Chroma 全库）。

        Args:
            question: 用户问题（自然语言）；可较长，但过长时建议拆成多次检索。
            pipeline: 管线 id，须为 topic4_list_rag_pipelines 列出之一。
        """
        pid = (pipeline or "project_default").strip().lower()
        if pid not in list_preset_ids():
            return (
                f"未知 pipeline={pipeline!r}。\n\n"
                + describe_presets()
            )
        profile = run_profile_for_preset(pid)
        q = (question or "").strip()
        from agentic_rag.experiment.session_rag import (
            get_combine_ephemeral_with_kb,
            get_ephemeral_session_index,
            run_combined_kb_ephemeral_rag,
            run_ephemeral_session_rag,
        )

        if get_ephemeral_session_index() is not None and get_combine_ephemeral_with_kb():
            print(
                "[rag] 全库 Chroma + 本会话临时索引（融合检索）",
                flush=True,
            )
            out = run_combined_kb_ephemeral_rag(
                q,
                profile,
                allowed_doc_ids=kb_doc_ids if kb_doc_ids else None,
            )
        elif get_ephemeral_session_index() is not None:
            print("[rag] 本会话临时索引检索（未写入全库 Chroma）", flush=True)
            out = run_ephemeral_session_rag(q, profile)
        elif use_kb:
            out = run_knowledge_base_rag(
                q,
                profile,
                allowed_doc_ids=kb_doc_ids if kb_doc_ids else None,
            )
        else:
            assert path_str is not None
            out = run_document_rag(path_str, q, profile)
        from agentic_rag.telemetry.audit_log import audit_record
        from agentic_rag.telemetry.audit_payload import rag_result_to_payload

        audit_record(
            "rag_query_result",
            payload={
                "pipeline": pid,
                "question": q,
                **rag_result_to_payload(out),
            },
        )
        return _compact_rag_result(out, pipeline=pid)

    tools: list[Any] = [
        topic4_list_rag_pipelines,
        topic4_rag_query,
        *_build_firecrawl_tools(enable_c4_tools=enable_c4_tools),
        *_build_c4_file_tools(enable_c4_tools=enable_c4_tools),
    ]
    if enable_c4_tools and sandbox_workspace is not None and app_config.SANDBOX_ENABLED:
        tools.append(_sandbox_python_tool(sandbox_workspace))

    from agentic_rag.telemetry.tool_audit import wrap_tools_with_audit

    return wrap_tools_with_audit(tools)
