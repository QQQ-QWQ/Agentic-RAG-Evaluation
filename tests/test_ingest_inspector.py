"""文档传入检查与审计日志测试。"""

from __future__ import annotations

from pathlib import Path

from agentic_rag.documents.ingest_inspector import (
    file_content_sha256,
    inspect_document_paths,
    resolve_session_doc_ids,
)
from agentic_rag.telemetry.audit_log import audit_log, default_audit_log_path


def test_same_content_different_paths_warning(tmp_path: Path):
    a = tmp_path / "a.md"
    b = tmp_path / "subdir" / "b.md"
    b.parent.mkdir(parents=True, exist_ok=True)
    text = "# hello\nsame content\n"
    a.write_text(text, encoding="utf-8")
    b.write_text(text, encoding="utf-8")
    assert file_content_sha256(a) == file_content_sha256(b)

    report = inspect_document_paths(
        paths_text=f"{a}\n{b}",
        project_root=tmp_path,
    )
    statuses = {f.status for f in report.files}
    assert "ok" in statuses or "duplicate_input" in statuses


def test_resolve_session_doc_ids_skips_duplicate_content(tmp_path: Path):
    a = tmp_path / "guide.md"
    a.write_text("# guide\n考核任务\n", encoding="utf-8")
    report = inspect_document_paths(paths_text=str(a), project_root=tmp_path)
    # 首次无库内重复 → 需入库
    doc_ids, to_ingest, warnings = resolve_session_doc_ids(report, skip_duplicate_content=True)
    assert to_ingest == [a.resolve()]
    assert doc_ids == []

    # 模拟库内已有同 hash
    from agentic_rag.experiment.kb_ingest import ingest_files_to_kb_batch

    ingest_files_to_kb_batch(tmp_path, [a], source_note="test")
    b = tmp_path / "copy_guide.md"
    b.write_text(a.read_text(encoding="utf-8"), encoding="utf-8")
    report2 = inspect_document_paths(paths_text=str(b), project_root=tmp_path)
    doc_ids2, to_ingest2, warnings2 = resolve_session_doc_ids(
        report2, skip_duplicate_content=True
    )
    assert to_ingest2 == []
    assert doc_ids2
    assert any("跳过重复入库" in w for w in warnings2)


def test_audit_log_append(tmp_path: Path):
    log_file = tmp_path / "audit.jsonl"
    audit_log("test_event", session_id="sess1", payload={"k": 1}, log_path=log_file)
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert "test_event" in lines[0]
    assert "sess1" in lines[0]
