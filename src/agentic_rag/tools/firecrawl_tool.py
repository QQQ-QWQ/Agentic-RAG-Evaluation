"""
[Firecrawl](https://docs.firecrawl.dev/zh/introduction) 网页抓取与搜索封装，供第二层 Agent 工具调用。

需 ``FIRECRAWL_API_KEY`` 与 ``uv sync --group agent``（``firecrawl-py``）。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from agentic_rag import config
from agentic_rag.tools.response_format import tool_response_json

_URL_RE = re.compile(r"^https?://", re.I)
# 从自然语言中抽取 http(s) 链接（第二层 C4 系统侧预解析）
_HTTP_URL_IN_TEXT = re.compile(
    r"https?://[^\s<>\"')\]]+",
    re.IGNORECASE,
)
_BARE_WWW_IN_TEXT = re.compile(
    r"(?:^|[\s(（「『\"'])((?:www\.)[a-z0-9][-a-z0-9.]*\.[a-z]{2,}[^\s<>\"')\]]*)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FirecrawlScrapeResult:
    ok: bool
    url: str
    markdown: str
    title: str
    metadata: dict[str, Any]
    error: str | None = None


@dataclass(frozen=True)
class FirecrawlSearchResult:
    ok: bool
    query: str
    items: list[dict[str, Any]]
    error: str | None = None


def firecrawl_configured() -> bool:
    return bool(config.FIRECRAWL_API_KEY and config.FIRECRAWL_API_KEY.strip())


def extract_http_urls_from_text(text: str) -> list[str]:
    """从用户自然语言中确定性抽取 URL（供 C4 第二层提示，不替代 Agent 判断）。"""
    found: list[str] = []
    for m in _HTTP_URL_IN_TEXT.finditer(text or ""):
        u = normalize_http_url(m.group(0).rstrip(".,;，。；)）]」'"))
        if u and u not in found:
            found.append(u)
    for m in _BARE_WWW_IN_TEXT.finditer(text or ""):
        u = normalize_http_url(m.group(1).rstrip(".,;，。；)）]」'"))
        if u and u not in found:
            found.append(u)
    return found


def format_scrape_tool_response(res: FirecrawlScrapeResult) -> str:
    hints: list[str] = []
    if res.ok:
        hints.append("正文在 data.markdown；请据此作答，勿编造未出现的网页内容。")
    return tool_response_json(
        "topic4_firecrawl_scrape",
        ok=res.ok,
        data={
            "url": res.url,
            "title": res.title,
            "markdown": res.markdown,
            "metadata": res.metadata,
        },
        error=res.error,
        hints=hints,
    )


def format_search_tool_response(res: FirecrawlSearchResult) -> str:
    hints: list[str] = []
    if res.ok and res.items:
        hints.append("可对 items[].url 再调用 topic4_firecrawl_scrape 获取全文。")
    return tool_response_json(
        "topic4_firecrawl_search",
        ok=res.ok,
        data={"query": res.query, "items": res.items},
        error=res.error,
        hints=hints,
    )


def normalize_http_url(url: str) -> str | None:
    raw = (url or "").strip().strip('"').strip("'")
    if not raw:
        return None
    if not _URL_RE.match(raw):
        raw = "https://" + raw
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return raw


def _max_output_chars(cap: int | None = None) -> int:
    base = int(config.FIRECRAWL_MAX_OUTPUT_CHARS)
    if cap is None:
        return base
    try:
        c = int(cap)
    except (TypeError, ValueError):
        return base
    return max(2_000, min(c, base))


def _clip_text(text: str, max_chars: int) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 20] + "\n…(truncated)"


def _extract_scrape_payload(doc: Any) -> tuple[str, str, dict[str, Any]]:
    """从 Firecrawl SDK 返回中取出 markdown / title / metadata。"""
    markdown = ""
    title = ""
    meta: dict[str, Any] = {}
    if doc is None:
        return markdown, title, meta
    if isinstance(doc, dict):
        markdown = str(doc.get("markdown") or doc.get("content") or "")
        meta = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
        title = str(meta.get("title") or doc.get("title") or "")
        return markdown, title, meta
    markdown = str(getattr(doc, "markdown", None) or getattr(doc, "content", None) or "")
    meta_obj = getattr(doc, "metadata", None)
    if isinstance(meta_obj, dict):
        meta = meta_obj
    elif meta_obj is not None:
        meta = {
            k: getattr(meta_obj, k, None)
            for k in ("title", "description", "sourceURL", "statusCode", "language")
            if hasattr(meta_obj, k)
        }
    title = str(meta.get("title") or getattr(doc, "title", None) or "")
    return markdown, title, meta


def scrape_url(url: str, *, max_output_chars: int | None = None) -> FirecrawlScrapeResult:
    """抓取单个 URL，返回 Markdown 正文（供模型阅读，默认不入库）。"""
    normalized = normalize_http_url(url)
    if not normalized:
        return FirecrawlScrapeResult(
            ok=False,
            url=url,
            markdown="",
            title="",
            metadata={},
            error="无效的 http(s) URL",
        )
    if not firecrawl_configured():
        return FirecrawlScrapeResult(
            ok=False,
            url=normalized,
            markdown="",
            title="",
            metadata={},
            error="未配置 FIRECRAWL_API_KEY（见 .env.example）",
        )
    cap = _max_output_chars(max_output_chars)
    try:
        from firecrawl import Firecrawl

        client = Firecrawl(api_key=config.FIRECRAWL_API_KEY)
        doc = client.scrape(normalized, formats=["markdown"])
    except Exception as exc:
        return FirecrawlScrapeResult(
            ok=False,
            url=normalized,
            markdown="",
            title="",
            metadata={},
            error=f"{type(exc).__name__}: {exc}",
        )
    markdown, title, meta = _extract_scrape_payload(doc)
    return FirecrawlScrapeResult(
        ok=True,
        url=normalized,
        markdown=_clip_text(markdown, cap),
        title=title,
        metadata=meta,
        error=None,
    )


def search_web(
    query: str,
    *,
    limit: int | None = None,
    max_output_chars: int | None = None,
) -> FirecrawlSearchResult:
    """网页搜索；返回条目列表（含 url、title、description 等）。"""
    q = (query or "").strip()
    if not q:
        return FirecrawlSearchResult(ok=False, query="", items=[], error="query 为空")
    if not firecrawl_configured():
        return FirecrawlSearchResult(
            ok=False,
            query=q,
            items=[],
            error="未配置 FIRECRAWL_API_KEY",
        )
    lim = limit if limit is not None else int(config.FIRECRAWL_SEARCH_LIMIT)
    lim = max(1, min(int(lim), 10))
    cap = _max_output_chars(max_output_chars)
    try:
        from firecrawl import Firecrawl

        client = Firecrawl(api_key=config.FIRECRAWL_API_KEY)
        raw = client.search(q, limit=lim)
    except Exception as exc:
        return FirecrawlSearchResult(
            ok=False,
            query=q,
            items=[],
            error=f"{type(exc).__name__}: {exc}",
        )
    items = _normalize_search_items(raw)
    # 控制总 JSON 体积
    blob = json.dumps(items, ensure_ascii=False)
    if len(blob) > cap:
        trimmed: list[dict[str, Any]] = []
        used = 2
        for it in items:
            piece = json.dumps(it, ensure_ascii=False)
            if used + len(piece) > cap - 20:
                break
            trimmed.append(it)
            used += len(piece)
        items = trimmed
    return FirecrawlSearchResult(ok=True, query=q, items=items, error=None)


def _normalize_search_items(raw: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    data = raw
    if hasattr(raw, "data"):
        data = getattr(raw, "data")
    if isinstance(data, dict):
        web = data.get("web") or data.get("results") or []
        if isinstance(web, list):
            for row in web:
                if isinstance(row, dict):
                    out.append(
                        {
                            "url": row.get("url"),
                            "title": row.get("title"),
                            "description": row.get("description"),
                            "position": row.get("position"),
                        }
                    )
        return out
    if isinstance(raw, list):
        for row in raw:
            if isinstance(row, dict):
                out.append(dict(row))
    return out


def scrape_to_markdown_file(
    url: str,
    *,
    project_root: Path | None = None,
    title: str | None = None,
) -> tuple[Path | None, dict[str, Any]]:
    """
    抓取 URL 并将 Markdown 写入 ``data/raw/web_snapshots/``，供 ``topic4_file_ingest`` 使用。

    返回 ``(path, report)``；失败时 path 为 None。
    """
    root = (project_root or config.PROJECT_ROOT).resolve()
    res = scrape_url(url)
    report: dict[str, Any] = {
        "ok": res.ok,
        "url": res.url,
        "error": res.error,
    }
    if not res.ok:
        return None, report
    digest = hashlib.sha256(res.url.encode("utf-8")).hexdigest()[:12]
    safe_title = re.sub(r'[<>:"/\\|?*]', "_", (title or res.title or "web_page")[:80])
    out_dir = root / "data" / "raw" / "web_snapshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{safe_title}_{digest}.md"
    header = (
        f"# {title or res.title or 'Web snapshot'}\n\n"
        f"> Source: {res.url}\n"
        f"> Fetched via Firecrawl\n\n"
    )
    out_path.write_text(header + res.markdown, encoding="utf-8")
    report["saved_path"] = str(out_path)
    report["relative_path"] = str(out_path.relative_to(root)).replace("\\", "/")
    return out_path, report
