"""LLM Provider 抽象接口。"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional


class LLMProvider(ABC):
    """统一的 LLM 调用接口。"""

    @abstractmethod
    async def chat_completion(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> str:
        """发送消息，返回文本响应。"""
        ...


def create_llm_provider(provider_type: str, **kwargs) -> LLMProvider:
    """根据配置创建对应的 LLM Provider。"""
    if provider_type == "claude":
        from backend.llm.claude_provider import ClaudeProvider
        return ClaudeProvider(**kwargs)
    elif provider_type == "openai":
        from backend.llm.openai_provider import OpenAIProvider
        return OpenAIProvider(**kwargs)
    elif provider_type == "flue":
        from backend.llm.flue_provider import FlueProvider
        return FlueProvider(**kwargs)
    else:
        raise ValueError(f"不支持的 LLM Provider: {provider_type}")
