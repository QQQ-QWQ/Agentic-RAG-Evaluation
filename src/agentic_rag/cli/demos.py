"""交互演示与 Gradio UI：逻辑集中于此，供统一 CLI 调用；勿再新增根目录 demo 脚本。"""

from __future__ import annotations

import sys
from pathlib import Path

from agentic_rag import config
from agentic_rag.pipelines import answer_with_index, build_vector_index, local_rag_answer
from agentic_rag.pipelines.local_rag import run_c1_with_index


def _require_ark_deepseek() -> None:
    if not config.ARK_API_KEY:
        sys.exit("请配置 .env：ARK_API_KEY")
    if not config.DEEPSEEK_API_KEY:
        sys.exit("请配置 .env：DEEPSEEK_API_KEY")


def run_interactive_demo(initial_doc: str | None = None) -> None:
    """循环问答：建索引一次，多次提问（旧 demo.py）。"""
    _require_ark_deepseek()

    if initial_doc:
        doc_path = initial_doc.strip().strip('"')
    else:
        doc_path = input("请输入文档路径: ").strip().strip('"')

    if not doc_path:
        sys.exit("未指定文档路径")

    print("正在解析文档并建立向量索引…")
    index = build_vector_index(doc_path)
    n = len(index.chunks)
    print(f"索引完成，共 {n} 个文本块。随后可直接提问（仅问题会向量化，文档不重复索引）。")
    print("输入空行退出。\n")

    while True:
        try:
            q = input("问题> ").strip()
        except EOFError:
            break
        if not q:
            break
        try:
            ans = answer_with_index(index, q, top_k=4)
        except Exception as e:
            print(f"出错：{e}\n")
            continue
        print(ans)
        print()


def run_single_shot_rag(doc_path: str, question: str, *, top_k: int = 4) -> str:
    """单次：解析 → 索引 → 检索 → 生成（旧 rag_demo.py）。"""
    _require_ark_deepseek()
    return local_rag_answer(doc_path, question, top_k=top_k)


def run_c1_rewrite_once(
    doc_path: str,
    question: str,
    *,
    top_k: int = 5,
    log_dir: str | Path = "runs/logs",
    prompt_file: Path | None = None,
) -> dict:
    """单次 C1 改写链路（旧 c1_rewrite_demo.py）。"""
    _require_ark_deepseek()
    root = Path(__file__).resolve().parents[3]
    pf = prompt_file or (root / "prompts" / "query_rewrite_prompt.md")
    index = build_vector_index(doc_path)
    return run_c1_with_index(
        index,
        question,
        top_k=top_k,
        log_dir=str(log_dir),
        prompt_file=pf,
    )


def launch_gradio_ui(host: str = "127.0.0.1", port: int | None = None) -> None:
    """浏览器上传 + 问答（旧 upload_demo.py）。"""
    import time

    from agentic_rag.cli.gradio_launch import (
        DEFAULT_GRADIO_LEGACY_UI_PORT,
        launch_topic4_gradio,
    )
    from agentic_rag.telemetry.audit_log import audit_log, new_audit_session_id, set_audit_session_id
    from agentic_rag.telemetry.session_analytics import log_legacy_rag_turn

    listen_port = port if port is not None else DEFAULT_GRADIO_LEGACY_UI_PORT
    import gradio as gr

    def _file_path(file: object) -> str:
        if file is None:
            return ""
        if isinstance(file, (str, Path)):
            return str(file)
        return str(getattr(file, "name", file))

    def _ensure_session(session_id: str) -> str:
        sid = (session_id or "").strip()
        if sid:
            return sid
        sid = new_audit_session_id()
        set_audit_session_id(sid)
        audit_log(
            "legacy_rag_session_start",
            session_id=sid,
            payload={"module": "legacy_rag", "ui": "upload_demo"},
        )
        return sid

    def run_rag(file: object, question: str, top_k: float, session_id: str):
        path = _file_path(file)
        if not path:
            return ("请先上传文档（pdf、docx、txt、md）。", session_id, session_id or "", "")
        q = (question or "").strip()
        if not q:
            return ("请输入问题。", session_id, session_id or "", "")
        if not config.ARK_API_KEY:
            return ("请配置 .env：ARK_API_KEY", session_id, session_id or "", "")
        if not config.DEEPSEEK_API_KEY:
            return ("请配置 .env：DEEPSEEK_API_KEY", session_id, session_id or "", "")
        k = int(top_k) if top_k else 4
        sid = _ensure_session(session_id)
        t0 = time.perf_counter()
        try:
            answer = local_rag_answer(path, q, top_k=k)
        except Exception as e:
            answer = f"执行出错：{e}"
        latency_ms = int((time.perf_counter() - t0) * 1000)
        params = {"doc_path": path, "top_k": k, "pipeline": "c0_naive", "config": "legacy_ui"}
        if not answer.startswith("执行出错"):
            log_legacy_rag_turn(
                sid,
                user_text=q,
                assistant_text=answer,
                params=params,
                latency_ms=latency_ms,
            )
        return (
            answer,
            sid,
            sid,
            f"Session ID：`{sid}`（可在 main.py logs 页「可视化仪表盘」查看 trace）",
        )

    with gr.Blocks(title="Agentic RAG") as demo:
        gr.Markdown(
            "上传本地文档后输入问题。需配置 `.env`（方舟向量 + DeepSeek）。"
            "每轮问答写入 audit trace，可在 **main.py logs** 页查看图表。"
        )
        session_id_state = gr.State("")
        file_in = gr.File(
            label="上传文档",
            file_types=[".pdf", ".docx", ".txt", ".md", ".markdown"],
            type="filepath",
        )
        q_in = gr.Textbox(label="问题", lines=2)
        k_in = gr.Slider(1, 10, value=4, step=1, label="检索片段数 top_k")
        btn = gr.Button("提交", variant="primary")
        session_id_tb = gr.Textbox(label="Session ID（trace 追溯）", interactive=False)
        out = gr.Textbox(label="回答", lines=16)
        session_hint = gr.Markdown("")
        btn.click(
            run_rag,
            inputs=[file_in, q_in, k_in, session_id_state],
            outputs=[out, session_id_state, session_id_tb, session_hint],
        )

    launch_topic4_gradio(
        demo,
        host=host,
        port=listen_port,
        service_label="单文件上传 RAG（legacy ui）",
        peer_hint="C3/C4 客户端默认 7860，日志查看默认 7861",
    )
