"""
文档传入检查：解析路径、展示文件名、内容指纹与知识库指纹说明。

**不参与** 模型规划；供 UI 展示与审计日志。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentic_rag import config as app_config
from agentic_rag.documents.multi_doc import (
    parse_document_paths_from_text,
    resolve_document_paths,
)


def file_content_sha256(path: Path) -> str:
    """流式计算文件 SHA256（用于「内容相同、路径不同」检测）。"""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


@dataclass
class FileIngestCheck:
    """单个待入库文件的检查结果。"""

    input_token: str
    resolved_path: Path | None = None
    file_name: str = ""
    size_bytes: int = 0
    content_sha256: str = ""
    status: str = "pending"  # ok | missing | duplicate_input | duplicate_content_in_kb
    existing_doc_ids: list[str] = field(default_factory=list)
    csv_rel_path: str = ""
    notes: list[str] = field(default_factory=list)


@dataclass
class IngestInspectReport:
    """一次传入批次的检查报告。"""

    files: list[FileIngestCheck] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    kb_fingerprint_before: str = ""
    kb_fingerprint_after_hint: str = ""
    will_force_rebuild: bool = False
    parse_tokens: list[str] = field(default_factory=list)

    @property
    def ok_paths(self) -> list[Path]:
        return [f.resolved_path for f in self.files if f.resolved_path and f.status == "ok"]

    def to_audit_payload(self) -> dict[str, Any]:
        return {
            "errors": self.errors,
            "warnings": self.warnings,
            "kb_fingerprint_before": self.kb_fingerprint_before,
            "will_force_rebuild": self.will_force_rebuild,
            "files": [
                {
                    "input": f.input_token,
                    "path": str(f.resolved_path) if f.resolved_path else None,
                    "name": f.file_name,
                    "size": f.size_bytes,
                    "sha256": f.content_sha256[:16] + "…" if f.content_sha256 else "",
                    "status": f.status,
                    "doc_ids": f.existing_doc_ids,
                    "notes": f.notes,
                }
                for f in self.files
            ],
        }


def _kb_fingerprint(project_root: Path) -> str:
    from agentic_rag.experiment.kb_index_builder import kb_fingerprint

    csv_path = project_root / "data" / "processed" / "documents.csv"
    if not csv_path.is_file():
        return ""
    return kb_fingerprint(csv_path, project_root)


def _inventory_by_rel_and_hash(project_root: Path) -> tuple[dict[str, str], dict[str, list[str]]]:
    """rel_path -> doc_id；content_sha256 -> [doc_id,...]（仅对已登记且文件存在者算 hash）。"""
    from agentic_rag.experiment.kb_index_builder import read_csv_rows

    csv_path = project_root / "data" / "processed" / "documents.csv"
    by_rel: dict[str, str] = {}
    by_hash: dict[str, list[str]] = {}
    if not csv_path.is_file():
        return by_rel, by_hash
    for row in read_csv_rows(csv_path):
        rel = (row.get("file_path") or "").replace("\\", "/").strip()
        did = (row.get("doc_id") or "").strip()
        if not rel or not did:
            continue
        by_rel[rel] = did
        fp = (project_root / rel).resolve()
        if fp.is_file():
            try:
                digest = file_content_sha256(fp)
                by_hash.setdefault(digest, []).append(did)
            except OSError:
                pass
    return by_rel, by_hash


def inspect_document_paths(
    *,
    paths_text: str | None = None,
    explicit_paths: list[str] | None = None,
    project_root: Path | None = None,
) -> IngestInspectReport:
    """
  解析并检查待传入文件（不入库）。

  指纹说明见 ``format_ingest_report_markdown`` 文末。
  """
    root = (project_root or app_config.PROJECT_ROOT).resolve()
    report = IngestInspectReport()
    report.kb_fingerprint_before = _kb_fingerprint(root)

    tokens: list[str] = []
    if explicit_paths:
        tokens.extend(p for p in explicit_paths if str(p).strip())
    if paths_text and str(paths_text).strip():
        for t in parse_document_paths_from_text(str(paths_text)):
            if t not in tokens:
                tokens.append(t)
    report.parse_tokens = list(tokens)

    if not tokens:
        report.warnings.append("未解析到任何文件路径；会话将使用 Chroma 全库。")
        return report

    resolved, errors = resolve_document_paths(tokens, project_root=root)
    report.errors.extend(errors)

    by_rel, by_hash = _inventory_by_rel_and_hash(root)
    seen_abs: dict[str, FileIngestCheck] = {}
    seen_hash_in_batch: dict[str, str] = {}

    for token in tokens:
        check = FileIngestCheck(input_token=token)
        t = token.strip().strip('"').strip("'")
        p = Path(t).expanduser()
        if not p.is_absolute():
            p = (root / p).resolve()
        else:
            p = p.resolve()
        if not p.is_file():
            check.status = "missing"
            report.files.append(check)
            continue
        check.resolved_path = p
        check.file_name = p.name
        check.size_bytes = p.stat().st_size
        try:
            check.content_sha256 = file_content_sha256(p)
        except OSError as exc:
            check.status = "missing"
            check.notes.append(str(exc))
            continue

        abs_key = str(p)
        if abs_key in seen_abs:
            check.status = "duplicate_input"
            check.notes.append(f"与本批次重复：{seen_abs[abs_key].file_name}")
            continue
        seen_abs[abs_key] = check

        if check.content_sha256 in seen_hash_in_batch:
            check.status = "duplicate_input"
            check.notes.append(
                f"与本批次另一路径内容相同（sha256 前缀 {check.content_sha256[:12]}…）"
            )
            continue
        seen_hash_in_batch[check.content_sha256] = abs_key

        try:
            rel = str(p.relative_to(root)).replace("\\", "/")
            check.csv_rel_path = rel
            if rel in by_rel:
                check.existing_doc_ids.append(by_rel[rel])
                check.notes.append(f"CSV 已登记为 {by_rel[rel]}（路径一致）")
        except ValueError:
            check.notes.append("文件在工程根外，入库时将复制到 data/raw/user_docs/")

        if check.content_sha256 in by_hash:
            ids = by_hash[check.content_sha256]
            for did in ids:
                if did not in check.existing_doc_ids:
                    check.existing_doc_ids.append(did)
            if check.status == "pending":
                check.status = "duplicate_content_in_kb"
                check.notes.append(
                    f"内容与库内 doc_id {', '.join(ids)} 相同；"
                    "默认将复用已有 doc_id，不再重复入库"
                )
        if check.status == "pending":
            check.status = "ok"
        report.files.append(check)

    ok_count = sum(1 for f in report.files if f.status == "ok")
    dup_content = sum(1 for f in report.files if f.status == "duplicate_content_in_kb")
    if ok_count:
        report.will_force_rebuild = True
        report.kb_fingerprint_after_hint = (
            "入库后将更新 documents.csv 并 force_rebuild Chroma；"
            "指纹 = CSV 各行路径文件的 mtime/size + 切块参数 + embedding 模型，"
            "**与文件内容 hash 无直接对应**。"
        )
    elif dup_content:
        report.will_force_rebuild = False
        report.kb_fingerprint_after_hint = (
            "检测到与库内内容相同：会话将复用已有 doc_id，**不会**新增 CSV 行或重建 Chroma。"
        )
    return report


def resolve_session_doc_ids(
    report: IngestInspectReport,
    *,
    skip_duplicate_content: bool = True,
) -> tuple[list[str], list[Path], list[str]]:
    """
    根据检查结果决定：哪些文件需要新入库、哪些复用已有 doc_id。

    返回 ``(doc_ids, paths_for_display, warnings)``。
    """
    doc_ids: list[str] = []
    paths: list[Path] = []
    warnings: list[str] = []
    to_ingest: list[Path] = []

    for f in report.files:
        if f.resolved_path:
            paths.append(f.resolved_path)
        if f.status == "ok" and f.resolved_path:
            to_ingest.append(f.resolved_path)
        elif f.status == "duplicate_content_in_kb" and skip_duplicate_content:
            for did in f.existing_doc_ids:
                if did and did not in doc_ids:
                    doc_ids.append(did)
            warnings.append(
                f"已跳过重复入库：{f.file_name} → 复用 {', '.join(f.existing_doc_ids)}"
            )
        elif f.status == "duplicate_input":
            warnings.append(f"本批次重复路径已忽略：{f.file_name}")

    return doc_ids, to_ingest, warnings


def format_ingest_report_markdown(report: IngestInspectReport) -> str:
    """供 Gradio / 终端展示的检查报告（Markdown）。"""
    lines = ["### 传入文件检查", ""]
    if not report.files:
        lines.append("- （无文件）")
    else:
        lines.append("| 状态 | 文件名 | 绝对路径 | 大小 | 说明 |")
        lines.append("|------|--------|----------|------|------|")
        for f in report.files:
            path_s = f"`{f.resolved_path}`" if f.resolved_path else "—"
            size_s = f"{f.size_bytes:,} B" if f.size_bytes else "—"
            note = "; ".join(f.notes) if f.notes else "—"
            if f.existing_doc_ids:
                note = f"doc_id: {', '.join(f.existing_doc_ids)}; {note}"
            lines.append(
                f"| {f.status} | **{f.file_name or '—'}** | {path_s} | {size_s} | {note} |"
            )
    if report.errors:
        lines.extend(["", "**错误**", ""])
        for e in report.errors:
            lines.append(f"- {e}")
    if report.warnings:
        lines.extend(["", "**提示**", ""])
        for w in report.warnings:
            lines.append(f"- {w}")
    if report.kb_fingerprint_before:
        lines.extend(
            [
                "",
                f"**当前知识库指纹（前 16 位）**：`{report.kb_fingerprint_before[:16]}…`",
            ]
        )
    if report.kb_fingerprint_after_hint:
        lines.extend(["", report.kb_fingerprint_after_hint])
    lines.extend(
        [
            "",
            "#### 指纹与「同内容不同路径」",
            "",
            "- **路径 A 与路径 B 内容相同**：指纹仍按 **两条 CSV 记录、两个路径的 mtime/size** 计算；"
            " 默认会 **再入库一条 doc_id** 并 **重建索引**（本检查器会标 `duplicate_content_in_kb`）。",
            "- **同一路径、文件未改**：指纹不变 → 下次问答 **命中 Chroma，不重新切块**.",
            "- **同一路径、文件已修改**：mtime/size 变 → 指纹变 → 需重建索引。",
            "",
            f"审计日志（不参与模型）：`{app_config.PROJECT_ROOT}/runs/logs/audit/global_audit.jsonl`",
        ]
    )
    return "\n".join(lines)
