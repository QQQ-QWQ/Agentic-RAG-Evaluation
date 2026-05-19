"""CSV/表格统计（对应开题 C4 table_analyzer；不替代 MarkItDown 读 Office）。"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from agentic_rag import config
from agentic_rag.tools.response_format import tool_response_json

TableOp = Literal[
    "preview",
    "describe",
    "value_counts",
    "groupby_count",
    "column_mean",
]


def _load_table_dataframe(fp: Path) -> pd.DataFrame:
    """跳过 Markdown 前言，从首个像 CSV 表头的行开始解析（兼容 data/raw 内带 front matter 的文件）。"""
    lines = fp.read_text(encoding="utf-8").splitlines()
    start = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or s.startswith("#") or s.startswith(">") or s.startswith("---"):
            continue
        if "," in s and len(s.split(",")) >= 2:
            start = i
            break
    body = "\n".join(lines[start:])
    sep = "\t" if fp.suffix.lower() == ".tsv" else ","
    return pd.read_csv(StringIO(body), sep=sep)


def _resolve_csv_path(file_path: str, *, project_root: Path | None = None) -> Path:
    root = (project_root or config.PROJECT_ROOT).resolve()
    raw = (file_path or "").strip().strip('"').strip("'")
    if not raw:
        raise ValueError("file_path 为空")
    fp = Path(raw).expanduser()
    if not fp.is_absolute():
        fp = (root / fp).resolve()
    else:
        fp = fp.resolve()
    if not fp.is_file():
        raise FileNotFoundError(f"文件不存在：{fp}")
    if fp.suffix.lower() not in (".csv", ".tsv"):
        raise ValueError("table_analyzer 仅支持 .csv / .tsv")
    return fp


def analyze_table(
    file_path: str,
    operation: TableOp = "preview",
    *,
    column: str = "",
    group_by: str = "",
    top_n: int = 20,
    project_root: Path | None = None,
) -> dict[str, Any]:
    fp = _resolve_csv_path(file_path, project_root=project_root)
    df = _load_table_dataframe(fp)
    op = (operation or "preview").strip().lower()
    top_n = max(1, min(int(top_n), 200))

    if op == "preview":
        return {
            "ok": True,
            "path": str(fp),
            "rows": int(len(df)),
            "columns": list(df.columns.astype(str)),
            "head": df.head(min(5, len(df))).to_dict(orient="records"),
        }
    if op == "describe":
        desc = df.describe(include="all").fillna("").astype(str)
        return {
            "ok": True,
            "path": str(fp),
            "describe": desc.to_dict(),
        }
    col = (column or "").strip()
    if op == "value_counts":
        if not col or col not in df.columns:
            raise ValueError(f"请指定有效 column；可选：{list(df.columns)}")
        vc = df[col].astype(str).value_counts().head(top_n)
        return {
            "ok": True,
            "path": str(fp),
            "column": col,
            "value_counts": {str(k): int(v) for k, v in vc.items()},
        }
    if op == "groupby_count":
        gcol = (group_by or column or "").strip()
        if not gcol or gcol not in df.columns:
            raise ValueError(f"请指定有效 group_by/column；可选：{list(df.columns)}")
        gc = df.groupby(gcol, dropna=False).size().sort_values(ascending=False).head(top_n)
        return {
            "ok": True,
            "path": str(fp),
            "group_by": gcol,
            "counts": {str(k): int(v) for k, v in gc.items()},
        }
    if op == "column_mean":
        if not col or col not in df.columns:
            raise ValueError(f"请指定数值列 column；可选：{list(df.columns)}")
        series = pd.to_numeric(df[col], errors="coerce")
        return {
            "ok": True,
            "path": str(fp),
            "column": col,
            "mean": float(series.mean()),
            "count_numeric": int(series.notna().sum()),
        }
    raise ValueError(f"未知 operation={operation!r}")


def format_table_analyzer_response(payload: dict[str, Any]) -> str:
    return tool_response_json(
        "topic4_table_analyzer",
        ok=bool(payload.get("ok")),
        data={k: v for k, v in payload.items() if k not in ("ok", "error")},
        error=str(payload.get("error") or "") or None,
        hints=[
            "专用于 CSV 统计；读 PDF/Word 请用 topic4_file_read（根内可走 MarkItDown）。",
        ],
    )
