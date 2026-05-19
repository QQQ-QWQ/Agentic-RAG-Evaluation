"""
多文档绑定：从自然语言/列表解析路径 → 入库 documents.csv + Chroma → 按 doc_id 限定检索。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentic_rag import config as app_config

_EXT = r"(?:md|markdown|txt|pdf|docx?|pptx?|html|htm|csv|json|py|yaml|yml|xml)"
_PATH_IN_QUOTES = re.compile(
    rf'"([^"]+\.{_EXT})"|\'([^\']+\.{_EXT})\'',
    re.IGNORECASE,
)
_PATH_TOKEN = re.compile(
    rf"(?:[A-Za-z]:[\\/]|\.{0,2}[\\/])[^\s,;，；\n\"'<>|]+?\.{_EXT}",
    re.IGNORECASE,
)
_DATA_REL = re.compile(
    rf"data[\\/][^\s,;，；\n\"'<>|]+?\.{_EXT}",
    re.IGNORECASE,
)

RETRIEVAL_FULL_KB = "full_kb"
RETRIEVAL_EPHEMERAL_ONLY = "ephemeral_only"
RETRIEVAL_FULL_KB_AND_EPHEMERAL = "full_kb_and_ephemeral"

RETRIEVAL_MODE_LABELS: dict[str, str] = {
    RETRIEVAL_FULL_KB: "仅系统全库（Chroma）",
    RETRIEVAL_EPHEMERAL_ONLY: "仅本会话附加文件（临时索引）",
    RETRIEVAL_FULL_KB_AND_EPHEMERAL: "全库 + 附加文件（推荐）",
}


def normalize_retrieval_mode(mode: str | None, *, has_attachments: bool) -> str:
    """校验检索范围；有附加文件且未指定时默认「全库+附加」。"""
    if not has_attachments:
        return RETRIEVAL_FULL_KB
    raw = (mode or "").strip().lower()
    if raw in (
        RETRIEVAL_FULL_KB,
        RETRIEVAL_EPHEMERAL_ONLY,
        RETRIEVAL_FULL_KB_AND_EPHEMERAL,
    ):
        return raw
    if raw in ("combined", "merge", "both", "full+ephemeral"):
        return RETRIEVAL_FULL_KB_AND_EPHEMERAL
    return RETRIEVAL_FULL_KB_AND_EPHEMERAL


@dataclass
class SessionDocumentScope:
    """
    会话检索范围：

    - ``use_ephemeral``：本会话附加文件的内存索引（不写全库 Chroma）。
    - ``retrieval_mode``：``full_kb`` / ``ephemeral_only`` / ``full_kb_and_ephemeral``。
    - 否则 ``doc_ids`` 为空 → 全库；非空 → Chroma 子集。
    """

    doc_ids: list[str] = field(default_factory=list)
    retrieval_mode: str = RETRIEVAL_FULL_KB
    source_paths: list[Path] = field(default_factory=list)
    ingest_report: dict[str, Any] = field(default_factory=dict)
    inspect_markdown: str = ""
    use_ephemeral: bool = False
    ephemeral_meta: dict[str, Any] = field(default_factory=dict)
    ephemeral_index: Any = None  # SimpleVectorIndex，仅 use_ephemeral 时非空

    @property
    def use_full_kb(self) -> bool:
        return (
            not self.doc_ids
            and not self.use_ephemeral
            and self.retrieval_mode == RETRIEVAL_FULL_KB
        )

    @property
    def combine_ephemeral_with_full_kb(self) -> bool:
        return (
            self.use_ephemeral
            and self.retrieval_mode == RETRIEVAL_FULL_KB_AND_EPHEMERAL
        )

    def summary_for_ui(self) -> str:
        if self.use_ephemeral and self.combine_ephemeral_with_full_kb:
            n = self.ephemeral_meta.get("chunk_count", "?")
            return (
                "检索范围：**系统全库 Chroma + 本会话附加临时索引**（单次 RAG 融合检索）\n"
                f"- 附加文件数：{self.ephemeral_meta.get('file_count', len(self.source_paths))}\n"
                f"- 附加块数：{n}"
            )
        if self.use_ephemeral:
            n = self.ephemeral_meta.get("chunk_count", "?")
            return (
                "检索范围：**仅本会话临时索引**（未写入 documents.csv / 全库 Chroma）\n"
                f"- 文件数：{self.ephemeral_meta.get('file_count', len(self.source_paths))}\n"
                f"- 块数：{n}"
            )
        if self.use_full_kb:
            return "检索范围：Chroma 全库（系统知识库，见 data/processed/documents.csv）"
        names = ", ".join(self.doc_ids[:8])
        if len(self.doc_ids) > 8:
            names += f" … 共 {len(self.doc_ids)} 篇"
        paths = "\n".join(f"- `{p}`" for p in self.source_paths[:6])
        if len(self.source_paths) > 6:
            paths += f"\n- … 另有 {len(self.source_paths) - 6} 个文件"
        return (
            f"检索范围：已入库 Chroma 子集（doc_id: {names}）\n"
            f"{paths}"
        )


def parse_document_paths_from_text(text: str) -> list[str]:
    """
    从逗号/分号/换行分隔列表或自然语言句子中提取疑似文件路径。
    """
    raw = (text or "").strip()
    if not raw:
        return []

    found: list[str] = []

    def _add(token: str) -> None:
        t = token.strip().strip('"').strip("'").strip()
        if t and t not in found:
            found.append(t)

    for m in _PATH_IN_QUOTES.finditer(raw):
        _add(m.group(1) or m.group(2) or "")
    for m in _DATA_REL.finditer(raw):
        _add(m.group(0))
    for m in _PATH_TOKEN.finditer(raw):
        _add(m.group(0))

    for part in re.split(r"[,;，；\n]+", raw):
        p = part.strip().strip('"').strip("'")
        if not p:
            continue
        if re.search(rf"\.{_EXT}$", p, re.IGNORECASE) or p.startswith(("data/", "data\\")):
            _add(p)

    return found


def resolve_document_paths(
    tokens: list[str],
    *,
    project_root: Path | None = None,
) -> tuple[list[Path], list[str]]:
    """
    将路径 token 解析为存在的绝对路径。

    返回 ``(resolved, errors)``。
    """
    root = (project_root or app_config.PROJECT_ROOT).resolve()
    resolved: list[Path] = []
    errors: list[str] = []
    seen: set[str] = set()

    for token in tokens:
        t = (token or "").strip().strip('"').strip("'")
        if not t:
            continue
        p = Path(t).expanduser()
        if not p.is_absolute():
            p = (root / p).resolve()
        else:
            p = p.resolve()
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        if not p.is_file():
            errors.append(f"文件不存在：{p}")
            continue
        resolved.append(p)
    return resolved, errors


def lookup_doc_ids_for_paths(
    paths: list[Path],
    project_root: Path,
) -> list[str]:
    """在 documents.csv 中按 file_path 匹配已有 doc_id。"""
    from agentic_rag.experiment.kb_index_builder import read_csv_rows

    csv_path = project_root / "data" / "processed" / "documents.csv"
    if not csv_path.is_file() or not paths:
        return []
    rows = read_csv_rows(csv_path)
    by_rel: dict[str, str] = {}
    for row in rows:
        rel = (row.get("file_path") or "").replace("\\", "/").strip()
        did = (row.get("doc_id") or "").strip()
        if rel and did:
            by_rel[rel] = did

    out: list[str] = []
    for p in paths:
        try:
            rel = str(p.resolve().relative_to(project_root.resolve())).replace("\\", "/")
        except ValueError:
            continue
        did = by_rel.get(rel)
        if did and did not in out:
            out.append(did)
    return out


def build_session_document_scope(
    *,
    paths_text: str | None = None,
    explicit_paths: list[Path] | None = None,
    ingest_to_chroma: bool = False,
    retrieval_mode: str | None = None,
    session_id: str | None = None,
    project_root: Path | None = None,
) -> SessionDocumentScope:
    """
    解析路径 → 会话临时索引（默认）或（已废弃默认）全库入库。

    客户端附加文件：**不**写入 ``documents.csv``，仅 ``build_ephemeral_session_index``。
    无路径时返回系统全库检索范围。
    """
    root = (project_root or app_config.PROJECT_ROOT).resolve()
    tokens: list[str] = []
    if explicit_paths:
        tokens.extend(str(p) for p in explicit_paths)
    if paths_text and str(paths_text).strip():
        for t in parse_document_paths_from_text(str(paths_text)):
            if t not in tokens:
                tokens.append(t)

    if not tokens:
        return SessionDocumentScope()

    resolved, errors = resolve_document_paths(tokens, project_root=root)
    if errors and not resolved:
        return SessionDocumentScope(
            ingest_report={"ok": False, "errors": errors},
        )

    mode = normalize_retrieval_mode(
        retrieval_mode,
        has_attachments=True,
    )
    if mode == RETRIEVAL_FULL_KB:
        warnings = list(errors)
        warnings.append("检索范围为仅系统全库：未对附加文件建立临时索引。")
        return SessionDocumentScope(
            source_paths=resolved,
            retrieval_mode=RETRIEVAL_FULL_KB,
            ingest_report={"ok": True, "warnings": warnings},
        )

    if ingest_to_chroma:
        from agentic_rag.documents.ingest_inspector import (
            inspect_document_paths,
            resolve_session_doc_ids,
        )
        from agentic_rag.experiment.kb_ingest import ingest_files_to_kb_batch

        inspect = inspect_document_paths(
            paths_text=paths_text,
            explicit_paths=[Path(t) for t in tokens],
            project_root=root,
        )
        reused_ids, to_ingest, reuse_warnings = resolve_session_doc_ids(
            inspect,
            skip_duplicate_content=True,
        )
        ingest_report: dict[str, Any] = {
            "ok": True,
            "reused_doc_ids": reused_ids,
            "skipped_duplicate_ingest": len(resolved) - len(to_ingest),
        }
        if reuse_warnings:
            ingest_report["warnings"] = reuse_warnings
        if errors:
            ingest_report.setdefault("warnings", []).extend(errors)

        new_ids: list[str] = []
        if to_ingest:
            batch = ingest_files_to_kb_batch(
                root, to_ingest, source_note="CLI/legacy 全库入库"
            )
            new_ids = list(batch.get("doc_ids") or [])
            ingest_report.update(batch)

        doc_ids = list(dict.fromkeys([*reused_ids, *new_ids]))
        return SessionDocumentScope(
            doc_ids=doc_ids,
            source_paths=resolved,
            ingest_report=ingest_report,
            inspect_markdown="",
        )

    # 默认：会话临时索引（不写全库）
    from agentic_rag.documents.session_index import build_ephemeral_session_index

    label = (session_id or "session")[:16]
    index, ep_meta = build_ephemeral_session_index(
        resolved, session_label=label
    )
    if not ep_meta.get("ok"):
        return SessionDocumentScope(
            source_paths=resolved,
            ingest_report={"ok": False, "errors": errors, **ep_meta},
        )
    if errors:
        ep_meta.setdefault("warnings", []).extend(errors)

    return SessionDocumentScope(
        source_paths=resolved,
        ingest_report={"ok": True, "mode": "ephemeral", "retrieval_mode": mode, **ep_meta},
        use_ephemeral=True,
        retrieval_mode=mode,
        ephemeral_meta=ep_meta,
        ephemeral_index=index,
    )
