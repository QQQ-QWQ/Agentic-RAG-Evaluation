"""
知识库清单（``documents.csv``）只读查询：判断某工程内文件是否已登记。

用于编排层在 **不调用 embedding** 的前提下，向第二层提供「是否已向量化入库」的客观事实
（以清单为准；Chroma 内是否已有向量由 ``kb_index_builder`` 指纹决定，不在此重复探测）。
"""

from __future__ import annotations

import csv
from pathlib import Path


def _normalize_path_key(s: str) -> str:
    return str(s or "").strip().replace("\\", "/").lower()


def relative_path_under_project(project_root: Path, file_path: Path) -> str | None:
    """若 ``file_path`` 在 ``project_root`` 下，返回 posix 相对路径；否则 ``None``。"""
    try:
        root = project_root.resolve()
        fp = file_path.resolve()
        rel = fp.relative_to(root)
    except (OSError, ValueError):
        return None
    return rel.as_posix()


def file_path_registered_in_documents_csv(
    project_root: Path,
    file_path: Path,
    *,
    documents_csv: Path | None = None,
) -> bool:
    """
    当且仅当 ``documents.csv`` 的 ``file_path`` 列（规范化后）与 ``file_path`` 的工程相对路径一致时
    返回 True。
    """
    csv_path = documents_csv or (project_root / "data" / "processed" / "documents.csv")
    if not csv_path.is_file():
        return False
    rel = relative_path_under_project(project_root, file_path)
    if rel is None:
        return False
    want = _normalize_path_key(rel)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fp_col = row.get("file_path") or ""
            if _normalize_path_key(fp_col) == want:
                return True
    return False
