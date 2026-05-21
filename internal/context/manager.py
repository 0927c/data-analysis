"""ContextManager: 包装 ConversationManager，添加 token 感知消息历史管理与 Context Rot 防御。"""

import json
from typing import Optional

from backend.services.conversation_manager import ContextState, ConversationManager


class ContextManager:
    """
    在现有 ConversationManager 之上添加：
    - 消息历史追踪（用于 LLM context window）
    - Token 计数和窗口裁剪
    - 对话历史压缩策略（防 Context Rot）
    - 裁剪事件日志（供 SessionManager 记录）
    """

    def __init__(
        self,
        conversation_manager: ConversationManager,
        max_tokens: int = 8000,
        head_keep: int = 3,
        tail_keep: int = 5,
    ):
        self._cm = conversation_manager
        self._max_tokens = max_tokens
        self._head_keep = head_keep
        self._tail_keep = tail_keep
        # session_id → [{"role": str, "content": str}]
        self._histories: dict[int, list[dict]] = {}

    def get_filter_state(self, session_id: int) -> ContextState:
        """获取当前筛选状态，委托给 ConversationManager。"""
        return self._cm.get_context(session_id)

    def update_filters(self, session_id: int, new_filters: dict) -> ContextState:
        """更新筛选条件。"""
        return self._cm.update_context(session_id, new_filters)

    def reset_filters(self, session_id: int):
        """重置筛选条件。"""
        self._cm.reset_context(session_id)

    def add_message(self, session_id: int, role: str, content: str):
        """追加消息到历史。"""
        history = self._histories.setdefault(session_id, [])
        history.append({"role": role, "content": content})

    def get_history(self, session_id: int) -> list[dict]:
        """获取完整历史。"""
        return list(self._histories.get(session_id, []))

    def get_windowed_history(self, session_id: int) -> tuple[list[dict], dict]:
        """
        Token 感知窗口裁剪，防 Context Rot。
        策略：
        1. 如果总 token < max_tokens：返回完整历史
        2. 否则：保留 head N + tail M，中间压缩为摘要
        返回 (windowed_messages, prune_stats)
        """
        history = self._histories.get(session_id, [])
        if not history:
            return [], {"pruned": False, "before": 0, "after": 0}

        before_tokens = sum(_estimate_tokens(m["content"]) for m in history)

        if before_tokens <= self._max_tokens:
            return history, {"pruned": False, "before": before_tokens, "after": before_tokens}

        # Head + tail 保留
        head = history[: self._head_keep]
        remaining = history[self._head_keep:]

        if len(remaining) <= self._tail_keep:
            # 尾部不够，直接返回
            return history, {"pruned": False, "before": before_tokens, "after": before_tokens}

        # 中间段需要压缩
        middle = remaining[: -self._tail_keep]
        tail = remaining[-self._tail_keep:]

        summary = _summarize_middle(middle)
        result = head + [{"role": "system", "content": summary}] + tail
        after_tokens = sum(_estimate_tokens(m["content"]) for m in result)

        return result, {
            "pruned": True,
            "before": before_tokens,
            "after": after_tokens,
            "saved": before_tokens - after_tokens,
            "middle_messages": len(middle),
        }

    def save_context_to_db(self, session_id: int) -> str:
        """序列化上下文（filters + history 摘要）为 JSON，写入 DB。"""
        ctx = self._cm.get_context(session_id)
        return json.dumps(
            {
                "filters": ctx.active_filters,
                "datasource": ctx.current_datasource,
                "last_report_id": ctx.last_report_id,
                "last_chart_type": ctx.last_chart_type,
                "history_len": len(self._histories.get(session_id, [])),
            },
            ensure_ascii=False,
        )

    def force_prune(self, session_id: int) -> tuple[list[dict], dict]:
        """
        强制裁剪：无论是否超限，都执行 head + tail 策略。
        用于用户主动触发"清理上下文"。
        """
        history = self._histories.get(session_id, [])
        if not history:
            return [], {"pruned": False, "before": 0, "after": 0}

        before_tokens = sum(_estimate_tokens(m["content"]) for m in history)

        head = history[: self._head_keep]
        tail = history[-self._tail_keep:] if len(history) > self._head_keep + self._tail_keep else []
        middle = history[self._head_keep: -self._tail_keep] if len(history) > self._head_keep + self._tail_keep else []

        summary = _summarize_middle(middle) if middle else ""
        result = head + ([{"role": "system", "content": summary}] if summary else []) + tail
        after_tokens = sum(_estimate_tokens(m["content"]) for m in result)

        return result, {
            "pruned": True,
            "before": before_tokens,
            "after": after_tokens,
            "saved": before_tokens - after_tokens,
            "middle_messages": len(middle),
        }


def _estimate_tokens(text: str) -> int:
    """
    粗略 token 估算，无需 tiktoken 依赖。
    中文 ~1.3 token/字，英文 ~0.75 token/词。
    """
    if not text:
        return 0
    chinese_chars = sum(1 for c in text if "一" <= c <= "鿿")
    english_words = len(text.split())
    return int(chinese_chars * 1.3 + english_words * 0.75)


def _summarize_middle(messages: list[dict]) -> str:
    """将中间消息压缩为简短摘要。"""
    user_msgs = [m for m in messages if m["role"] == "user"]
    previews = [m["content"][:30] for m in user_msgs[:3]]
    return f"[{len(user_msgs)} 条历史消息已压缩] 用户曾询问: {'; '.join(previews)}"
