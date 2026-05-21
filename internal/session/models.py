"""Session 数据模型 — SessionRecord 包装现有 DB Session，LogEntry 用于 append-only 审计日志。"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class SessionRecord:
    """薄包装 backend.models.Session，供 harness 层使用。"""
    id: int
    user_id: int
    title: str
    context_state: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_db_model(cls, db_session) -> "SessionRecord":
        return cls(
            id=db_session.id,
            user_id=db_session.user_id,
            title=db_session.title or "",
            context_state=db_session.context_state or "",
            created_at=db_session.created_at,
            updated_at=db_session.updated_at,
        )


@dataclass
class TokenUsage:
    """记录 LLM 单次调用的 token 消耗。"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = ""

    @classmethod
    def from_api_response(cls, usage: dict) -> "TokenUsage":
        return cls(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            model=usage.get("model", ""),
        )


@dataclass
class LogEntry:
    """
    Append-only 日志条目，完整记录模型的 Token 吐出与每个动作的载荷。
    用于审计、回放和 token 成本分析。
    """
    session_id: int
    action: str            # user_message / agent_response / tool_call / skill_exec / llm_call / context_prune
    content: str           # JSON-serialized payload
    metadata: dict = field(default_factory=dict)
    token_usage: Optional[TokenUsage] = None  # LLM 调用时记录 prompt/completion/total tokens
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        d = {
            "session_id": self.session_id,
            "action": self.action,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }
        if self.token_usage:
            d["token_usage"] = {
                "prompt_tokens": self.token_usage.prompt_tokens,
                "completion_tokens": self.token_usage.completion_tokens,
                "total_tokens": self.token_usage.total_tokens,
                "model": self.token_usage.model,
            }
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "LogEntry":
        token_data = data.get("token_usage")
        return cls(
            session_id=data["session_id"],
            action=data["action"],
            content=data["content"],
            metadata=data.get("metadata", {}),
            token_usage=TokenUsage(**token_data) if token_data else None,
            created_at=datetime.fromisoformat(data["created_at"]),
        )

    def token_count(self) -> int:
        """便捷方法：获取本次动作消耗的总 token 数。"""
        return self.token_usage.total_tokens if self.token_usage else 0
