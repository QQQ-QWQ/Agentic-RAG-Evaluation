"""本地进程级沙箱（独立工作目录 + 超时）。非 Docker；适合验证小段 Python。"""

from agentic_rag.sandbox.local_subprocess import SandboxResult, exec_python_snippet

__all__ = ["SandboxResult", "exec_python_snippet"]
