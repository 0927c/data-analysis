"""Claude API Provider 适配器。"""

from typing import Optional

from anthropic import AsyncAnthropic

from backend.llm.base import LLMProvider


class ClaudeProvider(LLMProvider):
    def __init__(
        self,
        api_key: str = "",
        model: str = "claude-sonnet-4-6-20250514",
        base_url: Optional[str] = None,
    ):
        self.model = model
        kwargs = {}
        if api_key:
            kwargs['api_key'] = api_key
        if base_url:
            kwargs['base_url'] = base_url
        self.client = AsyncAnthropic(**kwargs)

    async def chat_completion(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> str:
        system = ""
        user_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                system = msg["content"]
            else:
                user_messages.append(msg)

        response = await self.client.messages.create(
            model=self.model,
            system=system if system else None,
            messages=user_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.content[0].text
