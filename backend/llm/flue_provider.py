"""
Flue Agent LLM Provider — 通过 HTTP 调用 Flue Agent 服务。
使用 urllib.request 替代 httpx（httpx 与 Windows Node.js 存在兼容性问题）。
"""

from __future__ import annotations
import json
import urllib.request
from typing import Optional

from backend.llm.base import LLMProvider


class FlueProvider(LLMProvider):
    """通过 Flue Agent 服务调用 LLM，Agent 负责模型管理和意图路由。"""

    def __init__(self, base_url: str = "http://localhost:3002", **kwargs):
        from backend.config import settings
        agent_url = getattr(settings, "FLUE_AGENT_URL", None) or base_url
        self.base_url = agent_url.rstrip("/")
        self.timeout = 90

    def _post(self, path: str, payload: dict, max_retries: int = 2) -> dict:
        """发送 POST 请求到 Flue Agent，支持重试。"""
        body = json.dumps(payload).encode("utf-8")
        last_err = None
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(
                    f"{self.base_url}{path}",
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                resp = urllib.request.urlopen(req, timeout=self.timeout)
                return json.loads(resp.read().decode("utf-8"))
            except Exception as e:
                last_err = e
                if attempt < max_retries - 1:
                    import time
                    time.sleep(1)
        raise last_err

    async def chat_completion(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """发送聊天请求到 Flue Agent。"""
        system_content = ""
        chat_history = []
        user_message = ""

        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            elif msg["role"] == "user" and not user_message:
                user_message = msg["content"]
            elif msg["role"] in ("user", "assistant"):
                chat_history.append(msg)

        payload = {
            "message": user_message,
            "chat_history": chat_history[-6:],
            "data_context": system_content,
        }

        data = await self._run_in_executor(self._post, "/agent/chat", payload)
        return data.get("message", "")

    async def parse_intent(self, message: str, context: dict = None) -> dict:
        """调用 Flue Agent 进行意图识别。"""
        payload = {"message": message, "context": context or {}}
        return await self._run_in_executor(self._post, "/agent/intent", payload)

    async def _run_in_executor(self, fn, *args):
        """在线程池中运行同步阻塞函数。"""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, fn, *args)

    async def close(self):
        pass
