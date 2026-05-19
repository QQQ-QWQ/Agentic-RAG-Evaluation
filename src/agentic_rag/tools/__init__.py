"""可插拔工具：MarkItDown、Firecrawl 等（与 ``documents.parse_path`` 默认解析并行）。"""

from agentic_rag.tools.firecrawl_tool import (
    FirecrawlScrapeResult,
    FirecrawlSearchResult,
    firecrawl_configured,
    normalize_http_url,
    scrape_url,
    search_web,
)
from agentic_rag.tools.markitdown_tool import (
    MarkdownConversionResult,
    convert_local_file_to_markdown_safe,
)

__all__ = [
    "FirecrawlScrapeResult",
    "FirecrawlSearchResult",
    "MarkdownConversionResult",
    "convert_local_file_to_markdown_safe",
    "firecrawl_configured",
    "normalize_http_url",
    "scrape_url",
    "search_web",
]
