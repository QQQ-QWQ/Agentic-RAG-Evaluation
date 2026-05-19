import os
from pathlib import Path

from dotenv import load_dotenv

# 项目根 = 与 pyproject.toml 同目录。解压仓库时 .env 有时放在上一层，一并尝试加载。
_root = Path(__file__).resolve().parents[2]
PROJECT_ROOT: Path = _root
# 仓库内 .env 优先覆盖环境中已存在的同名变量（避免 shell 里 export 了空字符串导致读不到密钥）
load_dotenv(_root / ".env", override=True)
load_dotenv(_root.parent / ".env", override=False)


def _env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    return v.strip()


# 火山方舟：多模态向量（POST .../embeddings/multimodal，纯文本项）
ARK_BASE_URL = _env("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
ARK_API_KEY = _env("ARK_API_KEY")
ARK_EMBEDDING_MODEL = _env(
    "ARK_EMBEDDING_MODEL", "doubao-embedding-vision-250615"
)
ARK_EMBEDDING_DIMENSIONS = int(_env("ARK_EMBEDDING_DIMENSIONS", "2048") or "2048")

# Chroma：向量持久化（命中缓存时跳过文档块向量化）
CHROMA_PERSIST_DIRECTORY = _env(
    "CHROMA_PERSIST_DIRECTORY", r"E:\agentic_rag_chroma"
)

# DeepSeek：OpenAI 兼容对话（规划 / Agent / RAG 生成）
# 未单独配置时沿用 .env.example 里的 OPENAI_API_KEY（兼容同一密钥填 OpenAI 风格变量名的情况）
DEEPSEEK_API_KEY = _env("DEEPSEEK_API_KEY") or _env("OPENAI_API_KEY")
DEEPSEEK_BASE_URL = _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_CHAT_MODEL = _env("DEEPSEEK_CHAT_MODEL", "deepseek-chat")

# 本地代码沙箱（subprocess + 独立工作目录，非 Docker）
# 设为 true 后方注册 sandbox_exec_python 工具；请在可信环境下使用。
SANDBOX_ENABLED = (_env("SANDBOX_ENABLED", "false") or "false").lower() in (
    "1",
    "true",
    "yes",
    "on",
)
SANDBOX_TIMEOUT_SEC = float(_env("SANDBOX_TIMEOUT_SEC", "60") or "60")
SANDBOX_MAX_CODE_CHARS = int(_env("SANDBOX_MAX_CODE_CHARS", "50000") or "50000")

# C4：工程内文本写盘 / 局部编辑（须路径在工程根内且未命中 path_policy 拒绝规则）
FILE_WRITE_ENABLED = (_env("FILE_WRITE_ENABLED", "true") or "true").lower() in (
    "1",
    "true",
    "yes",
    "on",
)

# C4：在工程根或会话沙箱目录执行受限 shell（PowerShell / sh）
SHELL_COMMAND_ENABLED = (_env("SHELL_COMMAND_ENABLED", "true") or "true").lower() in (
    "1",
    "true",
    "yes",
    "on",
)
SHELL_TIMEOUT_SEC = float(_env("SHELL_TIMEOUT_SEC", "60") or "60")

# Agent 工具 topic4_file_read（MarkItDown 分支）：单文件最大字节（防止一次读爆内存）
MARKITDOWN_MAX_FILE_BYTES = int(
    _env("MARKITDOWN_MAX_FILE_BYTES", str(25 * 1024 * 1024)) or str(25 * 1024 * 1024)
)

# Firecrawl（https://docs.firecrawl.dev/zh/introduction）网页抓取 / 搜索
FIRECRAWL_API_KEY = _env("FIRECRAWL_API_KEY")
FIRECRAWL_MAX_OUTPUT_CHARS = int(
    _env("FIRECRAWL_MAX_OUTPUT_CHARS", "80000") or "80000"
)
FIRECRAWL_SEARCH_LIMIT = int(_env("FIRECRAWL_SEARCH_LIMIT", "5") or "5")

# 更强隔离的远端沙箱（与本仓库 sandbox/local_subprocess.py 无自动集成，仅作架构备选）：
# CubeSandbox（KVM MicroVM、兼容 E2B API）需独立 Linux/KVM 部署；资源随沙箱规格与并发变化，
# 官方说明含性能与内存对比，见 README_zh：
# https://github.com/TencentCloud/CubeSandbox/blob/master/README_zh.md
