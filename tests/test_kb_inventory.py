from __future__ import annotations

import csv
from pathlib import Path

from agentic_rag.experiment.kb_inventory import (
    file_path_registered_in_documents_csv,
    relative_path_under_project,
)


def test_relative_path_under_project(tmp_path: Path) -> None:
    sub = tmp_path / "data" / "raw"
    sub.mkdir(parents=True)
    f = sub / "a.md"
    f.write_text("x", encoding="utf-8")
    assert relative_path_under_project(tmp_path, f) == "data/raw/a.md"


def test_file_path_registered_matches_backslash_column(tmp_path: Path) -> None:
    root = tmp_path
    doc = root / "notes" / "x.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("hi", encoding="utf-8")
    csv_path = root / "documents.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["doc_id", "title", "file_path", "doc_type", "source", "note"],
        )
        w.writeheader()
        w.writerow(
            {
                "doc_id": "doc_001",
                "title": "t",
                "file_path": r"notes\x.md",
                "doc_type": "md",
                "source": "s",
                "note": "",
            }
        )
    assert file_path_registered_in_documents_csv(root, doc, documents_csv=csv_path) is True


def test_file_path_registered_false_when_missing_row(tmp_path: Path) -> None:
    root = tmp_path
    doc = root / "only.md"
    doc.write_text("x", encoding="utf-8")
    csv_path = root / "documents.csv"
    csv_path.write_text(
        "doc_id,title,file_path,doc_type,source,note\n",
        encoding="utf-8",
    )
    assert file_path_registered_in_documents_csv(root, doc, documents_csv=csv_path) is False
