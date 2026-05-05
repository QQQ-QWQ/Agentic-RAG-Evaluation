from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    """解析结果，供后续分块、向量化使用。"""

    text: str
    path: str
    """绝对路径，便于日志与引用追溯。"""
    suffix: str
    """小写扩展名，如 .pdf、.docx。"""
