import os
from pathlib import Path

from dotenv import load_dotenv

# 项目根 = 与 pyproject.toml 同目录。解压仓库时 .env 有时放在上一层，一并尝试加载。
_root = Path(__file__).resolve().parents[2]
load_dotenv(_root / ".env")
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

# DeepSeek：OpenAI 兼容对话（RAG 生成）
DEEPSEEK_API_KEY = _env("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_CHAT_MODEL = _env("DEEPSEEK_CHAT_MODEL", "deepseek-chat")
