"""本地沙箱执行（无网络）。"""

import tempfile
from pathlib import Path

from agentic_rag.sandbox.local_subprocess import exec_python_snippet


def test_exec_python_snippet_runs() -> None:
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        r = exec_python_snippet(ws, "print('ok')\n")
        assert r.exit_code == 0
        assert "ok" in r.stdout
