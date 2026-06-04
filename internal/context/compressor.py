"""ContextCompressor: Token 感知上下文压缩，支持 LLM 和规则两种策略。"""

from __future__ import annotations
from typing import Optional

from backend.llm.base import LLMProvider


class ContextCompressor:
    """
    当对话历史超过 context window 时，压缩中间部分。
    LLM 不可用时自动降级为规则压缩。
    """

    def __init__(self, llm_provider: Optional[LLMProvider] = None, max_tokens: int = 4000):
        self._llm = llm_provider
        self._max_tokens = max_tokens

    async def compress(self, messages: list[dict]) -> str:
        """压缩消息列表为摘要字符串。"""
        if self._llm:
            return await self._compress_with_llm(messages)
        return self._compress_with_rules(messages)

    async def _compress_with_llm(self, messages: list[dict]) -> str:
        """使用 LLM 进行高质量压缩。"""
        system = "你是一个对话摘要助手。将以下对话历史压缩为简短的中文摘要，保留关键信息。不超过 200 字。"
        content = "\n".join(f'{m["role"]}: {m["content"]}' for m in messages)
        return await self._llm.chat_completion(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            temperature=0.2,
            max_tokens=512,
        )

    def _compress_with_rules(self, messages: list[dict]) -> str:
        """规则压缩：提取用户查询和筛选条件变更。"""
        user_queries = []
        for m in messages:
            if m["role"] == "user":
                user_queries.append(m["content"][:50])

        if not user_queries:
            return "[无历史消息]"

        recent = user_queries[-5:]
        return f"历史对话摘要: {'; '.join(recent)}"
