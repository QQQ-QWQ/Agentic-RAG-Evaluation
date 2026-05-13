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
from agentic_rag.tools.markitdown_tool import convert_local_file_to_markdown_safe


def _chunks_to_evidence_excerpt(raw: dict[str, Any], *, max_chars: int) -> str:
    chunks = raw.get("retrieved_chunks") or []
    parts: list[str] = []
    for i, ch in enumerate(chunks[:12]):
        if isinstance(ch, dict):
            t = (ch.get("text") or "").strip()
            cid = ch.get("chunk_id", "")
            parts.append(f"[{i + 1} chunk_id={cid}]\n{t}")
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


def build_topic4_rag_tools(
    doc_path: str | Path | None = None,
    *,
    use_knowledge_base: bool | None = None,
    sandbox_workspace: Path | None = None,
) -> list[Any]:
    """
    - ``topic4_list_rag_pipelines`` / ``topic4_rag_query`` / ``topic4_kb_ingest`` / ``topic4_file_to_markdown``
    - 可选 ``sandbox_exec_python``（``SANDBOX_ENABLED`` 且传入 ``sandbox_workspace``）

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
        if use_kb:
            out = run_knowledge_base_rag(q, profile)
        else:
            assert path_str is not None
            out = run_document_rag(path_str, q, profile)
        return _compact_rag_result(out, pipeline=pid)

    @tool
    def topic4_kb_ingest(file_path: str, title: str = "") -> str:
        """把本地文件纳入全库知识库：写入 documents.csv、复制到 data/raw/user_docs/，并重建向量索引。

        路径须落在工程根目录内（相对仓库根或绝对路径均可）。会调用方舟 embedding，可能较慢。
        """
        root = Path(app_config.PROJECT_ROOT).resolve()
        raw = (file_path or "").strip()
        if not raw:
            return json.dumps({"ok": False, "error": "file_path 为空"}, ensure_ascii=False)
        fp = Path(raw).expanduser()
        if not fp.is_absolute():
            fp = (Path.cwd() / fp).resolve()
        else:
            fp = fp.resolve()
        try:
            fp.relative_to(root)
        except ValueError:
            return json.dumps(
                {"ok": False, "error": "仅允许工程目录内的路径"},
                ensure_ascii=False,
                indent=2,
            )
        out = ingest_local_file_to_kb(
            root,
            fp,
            title=title.strip() or None,
            source_note="Deep Agent 工具入库",
        )
        return json.dumps(out, ensure_ascii=False, indent=2)

    @tool
    def topic4_file_to_markdown(file_path: str, max_output_chars: int = 120_000) -> str:
        """将工程内文件转为 Markdown（Microsoft MarkItDown，见 https://github.com/microsoft/markitdown）。

        适用于 PDF、Word、HTML、PPTX 等需统一转成可读 Markdown 再分析的场景；路径必须在工程根目录内。
        与 ``topic4_rag_query`` 不同：本工具直接读磁盘文件内容，不查 Chroma。

        Args:
            file_path: 工程内相对或绝对路径。
            max_output_chars: 返回正文最大字符数，防止上下文爆炸（默认 120000）。
        """
        root = Path(app_config.PROJECT_ROOT).resolve()
        try:
            cap = int(max_output_chars)
        except (TypeError, ValueError):
            cap = 120_000
        cap = max(4_000, min(cap, 500_000))
        res = convert_local_file_to_markdown_safe(
            file_path,
            project_root=root,
            max_output_chars=cap,
        )
        payload: dict[str, Any] = {
            "ok": res.error is None,
            "source_path": res.source_path,
            "markdown": res.text,
            "error": res.error,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    tools: list[Any] = [
        topic4_list_rag_pipelines,
        topic4_rag_query,
        topic4_kb_ingest,
        topic4_file_to_markdown,
    ]

    if sandbox_workspace is not None and app_config.SANDBOX_ENABLED:
        tools.append(_sandbox_python_tool(sandbox_workspace))

    return tools
