"""文档解析：本地文件 → 纯文本。"""

from agentic_rag.documents.errors import UnsupportedFormatError
from agentic_rag.documents.models import ParsedDocument
from agentic_rag.documents.parse import parse_path

__all__ = [
    "ParsedDocument",
    "UnsupportedFormatError",
    "parse_path",
]
