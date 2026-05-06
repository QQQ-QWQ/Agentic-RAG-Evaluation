"""实验场景下要求 Chat Completions 返回准确 usage，禁止「无用量继续跑」。"""

from __future__ import annotations


def require_deepseek_chat_usage(usage: dict[str, int], *, where: str) -> None:
    """DeepSeek/OpenAI 兼容响应必须在 ``usage`` 中给出 ``total_tokens``。"""
    if usage.get("total_tokens") is None:
        raise RuntimeError(
            f"{where}：接口响应缺少 usage.total_tokens，无法记录准确实验用量。"
            "请检查 DeepSeek API 版本与返回格式，或联系接口提供方。"
        )
