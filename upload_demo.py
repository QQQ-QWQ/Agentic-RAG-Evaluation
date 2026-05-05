"""
浏览器上传文档后 RAG 问答（Gradio）。

运行：uv run python upload_demo.py
默认 http://127.0.0.1:7860
"""

from __future__ import annotations

from pathlib import Path

import gradio as gr

from agentic_rag import config
from agentic_rag.pipelines import local_rag_answer


def _file_path(file) -> str:
    if file is None:
        return ""
    if isinstance(file, (str, Path)):
        return str(file)
    return str(getattr(file, "name", file))


def run_rag(file, question: str, top_k: float) -> str:
    path = _file_path(file)
    if not path:
        return "请先上传文档（pdf、docx、txt、md）。"
    q = (question or "").strip()
    if not q:
        return "请输入问题。"
    if not config.ARK_API_KEY:
        return "请配置 .env：ARK_API_KEY"
    if not config.DEEPSEEK_API_KEY:
        return "请配置 .env：DEEPSEEK_API_KEY"
    k = int(top_k) if top_k else 4
    try:
        return local_rag_answer(path, q, top_k=k)
    except Exception as e:
        return f"执行出错：{e}"


def main() -> None:
    with gr.Blocks(title="Agentic RAG") as demo:
        gr.Markdown(
            "上传本地文档后输入问题。需配置 `.env`（方舟向量 + DeepSeek）。"
        )
        file_in = gr.File(
            label="上传文档",
            file_types=[".pdf", ".docx", ".txt", ".md", ".markdown"],
            type="filepath",
        )
        q_in = gr.Textbox(label="问题", lines=2)
        k_in = gr.Slider(1, 10, value=4, step=1, label="检索片段数 top_k")
        btn = gr.Button("提交", variant="primary")
        out = gr.Textbox(label="回答", lines=16)
        btn.click(run_rag, inputs=[file_in, q_in, k_in], outputs=out)

    demo.launch(server_name="127.0.0.1")


if __name__ == "__main__":
    main()
