"""可插拔工具：MarkItDown 等（与 ``documents.parse_path`` 默认解析并行）。"""

from agentic_rag.tools.markitdown_tool import (
    MarkdownConversionResult,
    convert_local_file_to_markdown_safe,
)

__all__ = [
    "MarkdownConversionResult",
    "convert_local_file_to_markdown_safe",
]
