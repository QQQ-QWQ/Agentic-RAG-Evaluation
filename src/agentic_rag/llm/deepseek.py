"""DeepSeek 对话：OpenAI 兼容 HTTP 客户端。"""

from openai import OpenAI

from agentic_rag import config


def create_deepseek_client() -> OpenAI:
    if not config.DEEPSEEK_API_KEY:
        raise ValueError("未配置 DEEPSEEK_API_KEY")
    return OpenAI(
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_BASE_URL,
        timeout=60.0,
        max_retries=2,
    )
