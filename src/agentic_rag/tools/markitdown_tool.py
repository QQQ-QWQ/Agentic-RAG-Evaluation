"""
使用 Microsoft MarkItDown 将本地文件转为 Markdown 文本。

- 路径必须落在 ``project_root`` 内（与 ``topic4_kb_ingest`` 一致的安全边界）。
- 不替代 ``documents.parse_path``：RAG 切块仍走既有解析链；本模块供 **Agent 工具**按需读取 Office/PDF 等。

官方仓库：<https://github.com/microsoft/markitdown>
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agentic_rag import config


@dataclass(frozen=True)
class MarkdownConversionResult:
    text: str
    source_path: str
    error: str | None = None


def convert_local_file_to_markdown_safe(
    file_path: str | Path,
    *,
    project_root: Path | None = None,
    max_file_bytes: int | None = None,
    max_output_chars: int = 120_000,
) -> MarkdownConversionResult:
    """
    将工程内文件转为 Markdown；失败时 ``error`` 非空、``text`` 为空。

    ``enable_plugins=False`` 以降低第三方插件面；若某格式需插件，可后续改为可配置。
    """
    root = (project_root or config.PROJECT_ROOT).resolve()
    cap = max_file_bytes if max_file_bytes is not None else int(config.MARKITDOWN_MAX_FILE_BYTES)

    raw = Path(str(file_path or "").strip()).expanduser()
    if not raw.is_absolute():
        fp = (Path.cwd() / raw).resolve()
    else:
        fp = raw.resolve()

    try:
        fp.relative_to(root)
    except ValueError:
        return MarkdownConversionResult(
            "",
            str(fp),
            error="路径必须位于工程根目录内",
        )

    if not fp.is_file():
        return MarkdownConversionResult("", str(fp), error="不是已存在的文件")

    try:
        sz = fp.stat().st_size
    except OSError as exc:
        return MarkdownConversionResult("", str(fp), error=str(exc))

    if sz > cap:
        return MarkdownConversionResult(
            "",
            str(fp),
            error=f"文件过大（{sz} 字节 > 上限 {cap}），拒绝转换",
        )

    try:
        from markitdown import MarkItDown
    except ImportError as exc:
        return MarkdownConversionResult(
            "",
            str(fp),
            error=f"未安装 markitdown：{exc}（请 uv sync --group agent）",
        )

    try:
        result = MarkItDown(enable_plugins=False).convert_local(str(fp))
        text = (getattr(result, "text_content", None) or "").strip()
    except Exception as exc:
        return MarkdownConversionResult("", str(fp), error=f"转换失败：{exc}")

    if len(text) > max_output_chars:
        text = text[: max_output_chars - 30] + "\n\n…(truncated)"

    return MarkdownConversionResult(text=text, source_path=str(fp), error=None)
