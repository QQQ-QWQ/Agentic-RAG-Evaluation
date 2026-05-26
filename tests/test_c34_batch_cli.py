"""C3/C4 batch CLI surface tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_cli_module():
    path = Path(__file__).resolve().parents[1] / "run_c34_batch_eval.py"
    spec = importlib.util.spec_from_file_location("run_c34_batch_eval", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_c34_parser_accepts_conservative_and_c2_baseline_options():
    args = _load_cli_module().build_c34_batch_parser().parse_args(
        [
            "--tier",
            "c3",
            "--split",
            "ids",
            "--question-ids",
            "Q007,Q008",
            "--no-adaptive-route",
            "--c3-conservative-opt",
            "--force-rag-preset",
            "c2_stage3_context",
            "--result-csv",
            "runs/results/test.csv",
        ]
    )
    assert args.c3_conservative_opt is True
    assert args.force_rag_preset == "c2_stage3_context"
    assert str(args.result_csv).endswith("test.csv")
