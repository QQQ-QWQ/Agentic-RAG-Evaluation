"""C4 calculator / table_analyzer / code_runner 单元测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentic_rag.tools.calculator_tool import safe_calculate
from agentic_rag.tools.table_analyzer_tool import analyze_table


def test_calculator_basic():
    r = safe_calculate("(0.5 + 0.7) / 2")
    assert r["ok"] is True
    assert abs(r["result"] - 0.6) < 1e-9


def test_calculator_rejects_import():
    r = safe_calculate("__import__('os').system('echo')")
    assert r["ok"] is False


def test_table_analyzer_rag_eval_csv():
    root = Path(__file__).resolve().parents[1]
    csv_path = root / "data" / "raw" / "tables_csv" / "rag_eval_results.csv"
    if not csv_path.is_file():
        pytest.skip("rag_eval_results.csv 不存在")
    r = analyze_table(str(csv_path), operation="preview", project_root=root)
    assert r["ok"] is True
    assert r["rows"] >= 1
    assert "columns" in r


def test_c4_tools_registered_when_sandbox(tmp_path, monkeypatch):
    monkeypatch.setenv("SANDBOX_ENABLED", "true")
    from agentic_rag import config

    config.SANDBOX_ENABLED = True  # noqa: SLF001 — 测试覆盖

    from agentic_rag.deep_planning.tools_factory import build_topic4_rag_tools

    names = {getattr(t, "name", "") for t in build_topic4_rag_tools(enable_c4_tools=True, sandbox_workspace=tmp_path)}
    assert "topic4_calculator" in names
    assert "topic4_table_analyzer" in names
    assert "topic4_code_runner" in names
    assert "sandbox_exec_python" in names


def test_code_runner_stages_file(tmp_path, monkeypatch):
    monkeypatch.setenv("SANDBOX_ENABLED", "true")
    from agentic_rag import config

    config.SANDBOX_ENABLED = True  # noqa: SLF001

    root = Path(__file__).resolve().parents[1]
    csv_rel = "data/raw/tables_csv/rag_eval_results.csv"
    if not (root / csv_rel).is_file():
        pytest.skip("rag_eval_results.csv 不存在")

    from agentic_rag.tools.code_runner_tool import run_code_in_sandbox

    code = """
import csv
from pathlib import Path
p = Path('data/rag_eval_results.csv')
lines = [ln for ln in p.read_text(encoding='utf-8').splitlines() if ',' in ln and not ln.strip().startswith('#')]
print(len(lines) - 1)
"""
    payload = run_code_in_sandbox(
        code,
        tmp_path,
        read_only_paths=[csv_rel],
        timeout_sec=30,
    )
    assert payload.get("staged_files")
    assert payload.get("exit_code") == 0
    assert "stdout" in payload
