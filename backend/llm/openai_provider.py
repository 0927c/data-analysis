"""OpenAI-compatible API Provider 适配器（兼容 vLLM/Ollama）。"""

from typing import Optional

from openai import AsyncOpenAI

from backend.llm.base import LLMProvider


class OpenAIProvider(LLMProvider):
    def __init__(
        self,
        api_key: str = "",
        model: str = "qwen2.5-7b-instruct",
        base_url: str = "",
    ):
        self.model = model
        kwargs = {}
        if base_url:
            kwargs['base_url'] = base_url
        if api_key:
            kwargs['api_key'] = api_key
        self.client = AsyncOpenAI(**kwargs)

    async def chat_completion(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content
