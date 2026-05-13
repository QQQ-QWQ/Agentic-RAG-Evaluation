"""知识库增量入库（不写 Chroma / 不调 embedding）。"""

from pathlib import Path

from agentic_rag.experiment.kb_ingest import ingest_local_file_to_kb, next_doc_id


def test_next_doc_id_increment(tmp_path: Path) -> None:
    inv = tmp_path / "data" / "processed" / "documents.csv"
    inv.parent.mkdir(parents=True)
    inv.write_text(
        "doc_id,title,file_path,doc_type,source,note\n"
        "doc_001,a,data/raw/x.md,t,s,n\n",
        encoding="utf-8",
    )
    assert next_doc_id(inv) == "doc_002"


def test_next_doc_id_empty_inventory(tmp_path: Path) -> None:
    assert next_doc_id(tmp_path / "missing.csv") == "doc_001"


def test_ingest_copies_and_appends(tmp_path: Path) -> None:
    root = tmp_path
    proc = root / "data" / "processed"
    proc.mkdir(parents=True)
    (proc / "documents.csv").write_text(
        "doc_id,title,file_path,doc_type,source,note\n"
        "doc_001,Old,data/raw/x.md,t,s,n\n",
        encoding="utf-8",
    )
    src = tmp_path / "hello.txt"
    src.write_text("hello kb", encoding="utf-8")

    r = ingest_local_file_to_kb(root, src, force_rebuild_index=False)
    assert r["ok"] is True
    assert r["doc_id"] == "doc_002"
    assert "user_docs" in r["file_path"]

    text = (proc / "documents.csv").read_text(encoding="utf-8-sig")
    assert "doc_002" in text
    assert "hello_doc_002.txt" in r["file_path"]

    copied = root / Path(r["file_path"])
    assert copied.is_file()
    assert copied.read_text(encoding="utf-8") == "hello kb"
