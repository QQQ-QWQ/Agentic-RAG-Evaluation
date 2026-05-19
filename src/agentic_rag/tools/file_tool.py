"""
C4 本地文件工具底层：与 Firecrawl 网页工具对称，供 ``topic4_file_read`` / ``topic4_file_ingest`` 调用。

- **读取**：工程根内优先 [MarkItDown](https://github.com/microsoft/markitdown)；其余用 ``documents.parse_path``。
- **入库**：委托 ``ingest_local_file_to_kb``（盘外路径会复制到 ``data/raw/user_docs/``）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from agentic_rag import config
from agentic_rag.tools.markitdown_tool import convert_local_file_to_markdown_safe
from agentic_rag.tools.path_policy import (
    assert_write_path_allowed,
    normalize_user_path,
)
from agentic_rag.tools.response_format import tool_response_json

MAX_FILE_WRITE_CHARS = 500_000

ReadBackend = Literal["markitdown", "parse_path"]


@dataclass(frozen=True)
class FileReadResult:
    ok: bool
    path: str
    text: str
    suffix: str
    in_project_root: bool
    backend: ReadBackend | None
    error: str | None = None


def read_file_content(
    file_path: str,
    *,
    project_root: Path | None = None,
    max_output_chars: int | None = None,
) -> FileReadResult:
    """动态读取用户给出的本地路径（对话内路径或规划层 local_paths）。"""
    root = (project_root or config.PROJECT_ROOT).resolve()
    cap = max_output_chars if max_output_chars is not None else 120_000
    try:
        cap = int(cap)
    except (TypeError, ValueError):
        cap = 120_000
    cap = max(2_000, min(cap, 500_000))

    raw = (file_path or "").strip().strip('"').strip("'")
    if not raw:
        return FileReadResult(
            ok=False,
            path="",
            text="",
            suffix="",
            in_project_root=False,
            backend=None,
            error="file_path 为空",
        )

    fp = Path(raw).expanduser()
    if not fp.is_absolute():
        fp = (root / fp).resolve()
    else:
        fp = fp.resolve()

    if not fp.is_file():
        return FileReadResult(
            ok=False,
            path=str(fp),
            text="",
            suffix=fp.suffix.lower(),
            in_project_root=False,
            backend=None,
            error=f"文件不存在：{fp}",
        )

    try:
        in_root = fp.is_relative_to(root)
    except ValueError:
        in_root = False

    suffix = fp.suffix.lower()
    if in_root:
        md = convert_local_file_to_markdown_safe(
            fp, project_root=root, max_output_chars=cap
        )
        if md.error:
            return FileReadResult(
                ok=False,
                path=str(fp),
                text="",
                suffix=suffix,
                in_project_root=True,
                backend="markitdown",
                error=md.error,
            )
        return FileReadResult(
            ok=True,
            path=str(fp),
            text=md.text,
            suffix=suffix,
            in_project_root=True,
            backend="markitdown",
        )

    try:
        from agentic_rag.documents import parse_path

        doc = parse_path(fp)
        text = doc.text
    except Exception as exc:
        return FileReadResult(
            ok=False,
            path=str(fp),
            text="",
            suffix=suffix,
            in_project_root=False,
            backend="parse_path",
            error=f"{type(exc).__name__}: {exc}",
        )
    if len(text) > cap:
        text = text[: cap - 20] + "\n…(truncated)"
    return FileReadResult(
        ok=True,
        path=str(fp),
        text=text,
        suffix=suffix,
        in_project_root=False,
        backend="parse_path",
    )


def format_file_read_response(res: FileReadResult) -> str:
    hints: list[str] = []
    if res.ok:
        hints.append(
            f"正文在 data.text（backend={res.backend}）；仅用于本轮作答，勿编造未出现的内容。"
        )
        if not res.in_project_root:
            hints.append(
                "若要长期检索该文件，请改调 topic4_file_ingest 或会话开始前在路径框登记。"
            )
        else:
            hints.append("若要纳入 Chroma，请改调 topic4_file_ingest。")
    return tool_response_json(
        "topic4_file_read",
        ok=res.ok,
        data={
            "path": res.path,
            "suffix": res.suffix,
            "in_project_root": res.in_project_root,
            "backend": res.backend,
            "text": res.text,
        },
        error=res.error,
        hints=hints,
    )


def ingest_file_to_kb(
    file_path: str,
    *,
    project_root: Path | None = None,
    title: str = "",
    source_note: str = "C4 file_ingest 工具入库",
    copy_file: bool = False,
) -> dict[str, Any]:
    """将任意可读本地文件入库（盘外会自动复制到 data/raw/user_docs/）。"""
    from agentic_rag.experiment.kb_ingest import ingest_local_file_to_kb

    root = (project_root or config.PROJECT_ROOT).resolve()
    raw = (file_path or "").strip().strip('"').strip("'")
    if not raw:
        return {"ok": False, "error": "file_path 为空"}
    fp = Path(raw).expanduser()
    if not fp.is_absolute():
        fp = (root / fp).resolve()
    else:
        fp = fp.resolve()
    if not fp.is_file():
        return {"ok": False, "error": f"不是可读文件：{fp}"}
    return ingest_local_file_to_kb(
        root,
        fp,
        title=title.strip() or None,
        source_note=source_note,
        copy_file=copy_file,
    )


@dataclass(frozen=True)
class FileWriteResult:
    ok: bool
    path: str
    rel_path: str
    bytes_written: int
    mode: str
    error: str | None = None


def write_file_content(
    file_path: str,
    content: str,
    *,
    mode: Literal["overwrite", "append"] = "overwrite",
    project_root: Path | None = None,
    create_dirs: bool = True,
) -> FileWriteResult:
    """在工程根内创建或写入文本文件（受 path_policy 约束）。"""
    root = (project_root or config.PROJECT_ROOT).resolve()
    resolved = normalize_user_path(file_path, project_root=root)
    if not resolved.ok:
        return FileWriteResult(
            ok=False,
            path=file_path,
            rel_path="",
            bytes_written=0,
            mode=mode,
            error=resolved.error,
        )
    try:
        assert_write_path_allowed(resolved.rel_posix)
    except PermissionError as exc:
        return FileWriteResult(
            ok=False,
            path=str(resolved.path),
            rel_path=resolved.rel_posix,
            bytes_written=0,
            mode=mode,
            error=str(exc),
        )

    text = content if content is not None else ""
    if len(text) > MAX_FILE_WRITE_CHARS:
        return FileWriteResult(
            ok=False,
            path=str(resolved.path),
            rel_path=resolved.rel_posix,
            bytes_written=0,
            mode=mode,
            error=f"内容超过 {MAX_FILE_WRITE_CHARS} 字符限制",
        )

    fp = resolved.path
    if create_dirs:
        fp.parent.mkdir(parents=True, exist_ok=True)
    write_mode = "a" if mode == "append" else "w"
    try:
        with fp.open(write_mode, encoding="utf-8", newline="\n") as f:
            f.write(text)
        nbytes = len(text.encode("utf-8"))
    except OSError as exc:
        return FileWriteResult(
            ok=False,
            path=str(fp),
            rel_path=resolved.rel_posix,
            bytes_written=0,
            mode=mode,
            error=f"{type(exc).__name__}: {exc}",
        )
    return FileWriteResult(
        ok=True,
        path=str(fp),
        rel_path=resolved.rel_posix,
        bytes_written=nbytes,
        mode=mode,
    )


@dataclass(frozen=True)
class FileEditResult:
    ok: bool
    path: str
    rel_path: str
    replacements: int
    error: str | None = None


def edit_file_content(
    file_path: str,
    old_string: str,
    new_string: str,
    *,
    replace_all: bool = False,
    project_root: Path | None = None,
) -> FileEditResult:
    """在工程根内对文本文件做局部替换（须唯一匹配，除非 replace_all）。"""
    root = (project_root or config.PROJECT_ROOT).resolve()
    resolved = normalize_user_path(file_path, project_root=root)
    if not resolved.ok:
        return FileEditResult(
            ok=False,
            path=file_path,
            rel_path="",
            replacements=0,
            error=resolved.error,
        )
    try:
        assert_write_path_allowed(resolved.rel_posix)
    except PermissionError as exc:
        return FileEditResult(
            ok=False,
            path=str(resolved.path),
            rel_path=resolved.rel_posix,
            replacements=0,
            error=str(exc),
        )

    fp = resolved.path
    if not fp.is_file():
        return FileEditResult(
            ok=False,
            path=str(fp),
            rel_path=resolved.rel_posix,
            replacements=0,
            error=f"文件不存在：{fp}",
        )

    needle = old_string if old_string is not None else ""
    if not needle:
        return FileEditResult(
            ok=False,
            path=str(fp),
            rel_path=resolved.rel_posix,
            replacements=0,
            error="old_string 不能为空",
        )

    try:
        original = fp.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return FileEditResult(
            ok=False,
            path=str(fp),
            rel_path=resolved.rel_posix,
            replacements=0,
            error="仅支持 UTF-8 文本文件编辑",
        )

    count = original.count(needle)
    if count == 0:
        return FileEditResult(
            ok=False,
            path=str(fp),
            rel_path=resolved.rel_posix,
            replacements=0,
            error="未找到 old_string，未修改文件",
        )
    if count > 1 and not replace_all:
        return FileEditResult(
            ok=False,
            path=str(fp),
            rel_path=resolved.rel_posix,
            replacements=0,
            error=f"old_string 出现 {count} 次，请设 replace_all=true 或提供更精确的片段",
        )

    if replace_all:
        updated = original.replace(needle, new_string if new_string is not None else "")
        replacements = count
    else:
        updated = original.replace(needle, new_string if new_string is not None else "", 1)
        replacements = 1

    if len(updated) > MAX_FILE_WRITE_CHARS:
        return FileEditResult(
            ok=False,
            path=str(fp),
            rel_path=resolved.rel_posix,
            replacements=0,
            error=f"编辑后超过 {MAX_FILE_WRITE_CHARS} 字符限制",
        )

    try:
        fp.write_text(updated, encoding="utf-8", newline="\n")
    except OSError as exc:
        return FileEditResult(
            ok=False,
            path=str(fp),
            rel_path=resolved.rel_posix,
            replacements=0,
            error=f"{type(exc).__name__}: {exc}",
        )

    return FileEditResult(
        ok=True,
        path=str(fp),
        rel_path=resolved.rel_posix,
        replacements=replacements,
    )


def format_file_write_response(res: FileWriteResult) -> str:
    hints: list[str] = []
    if res.ok:
        hints.append("写入后若需纳入全库检索，可执行 main.py kb sync 或 topic4_file_ingest。")
    return tool_response_json(
        "topic4_file_write",
        ok=res.ok,
        data={
            "path": res.path,
            "rel_path": res.rel_path,
            "bytes_written": res.bytes_written,
            "mode": res.mode,
        },
        error=res.error,
        hints=hints,
    )


def format_file_edit_response(res: FileEditResult) -> str:
    hints: list[str] = []
    if res.ok:
        hints.append(f"已替换 {res.replacements} 处；大改内容可用 topic4_file_write。")
    return tool_response_json(
        "topic4_file_edit",
        ok=res.ok,
        data={
            "path": res.path,
            "rel_path": res.rel_path,
            "replacements": res.replacements,
        },
        error=res.error,
        hints=hints,
    )


def format_file_ingest_response(report: dict[str, Any]) -> str:
    ok = bool(report.get("ok"))
    hints: list[str] = []
    if ok:
        did = report.get("doc_id") or (report.get("ingest") or {}).get("doc_id")
        hints.append(
            f"已入库 doc_id={did}；后续请用 topic4_rag_query 检索，勿重复 ingest。"
        )
    return tool_response_json(
        "topic4_file_ingest",
        ok=ok,
        data=report,
        error=None if ok else str(report.get("error") or "入库失败"),
        hints=hints,
    )
