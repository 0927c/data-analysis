"""SessionManager: CRUD 操作 + append-only JSONL 日志 + Token 消耗追踪。"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import select

from internal.session.models import SessionRecord, LogEntry, TokenUsage


class SessionManager:
    """
    包装现有 Session/Message/AuditLog 表。
    日志写入 JSONL 文件（append-only），不与 DB 竞争。
    记录每次 LLM 调用的 token 吐出量，支持成本分析。
    """

    def __init__(self, db_session_factory, log_dir: Optional[Path] = None):
        self._session_factory = db_session_factory
        self._log_dir = log_dir or Path("backend/data/logs")
        self._log_dir.mkdir(parents=True, exist_ok=True)

    async def get_session(self, session_id: int, user_id: int) -> Optional[SessionRecord]:
        """查询现有 sessions 表，验证用户归属。"""
        from backend.models import Session
        async with self._session_factory() as db:
            result = await db.execute(
                select(Session).where(
                    Session.id == session_id,
                    Session.user_id == user_id,
                )
            )
            db_session = result.scalar_one_or_none()
            if db_session is None:
                return None
            return SessionRecord.from_db_model(db_session)

    async def create_session(self, user_id: int, title: str) -> SessionRecord:
        """插入新 session 到现有 sessions 表。"""
        from backend.models import Session
        async with self._session_factory() as db:
            new_session = Session(user_id=user_id, title=title[:200])
            db.add(new_session)
            await db.flush()
            record = SessionRecord.from_db_model(new_session)
            await db.commit()
            return record

    async def save_context_state(self, session_id: int, state_json: str):
        """持久化到 sessions.context_state 列（与 chat.py 共享）。"""
        from backend.models import Session
        async with self._session_factory() as db:
            result = await db.execute(
                select(Session).where(Session.id == session_id)
            )
            db_session = result.scalar_one_or_none()
            if db_session:
                db_session.context_state = state_json
                await db.commit()

    def append_log(self, entry: LogEntry):
        """写入 JSONL 文件。每行一个完整 JSON 对象。"""
        log_file = self._log_dir / f"session_{entry.session_id}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

    def read_log(self, session_id: int, limit: int = 100) -> list[LogEntry]:
        """读取最后 N 条日志。"""
        log_file = self._log_dir / f"session_{session_id}.jsonl"
        if not log_file.exists():
            return []
        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        entries = []
        for line in lines[-limit:]:
            if line.strip():
                try:
                    entries.append(LogEntry.from_dict(json.loads(line)))
                except (json.JSONDecodeError, KeyError):
                    continue
        return entries

    # ─── 便捷方法 ───────────────────────────────────────────────

    def log_user_message(self, session_id: int, message: str, metadata: Optional[dict] = None):
        """记录用户消息。"""
        self.append_log(LogEntry(
            session_id=session_id,
            action="user_message",
            content=message,
            metadata=metadata or {},
        ))

    def log_agent_response(self, session_id: int, response: dict, metadata: Optional[dict] = None):
        """记录 Agent 响应。"""
        import json as _json
        self.append_log(LogEntry(
            session_id=session_id,
            action="agent_response",
            content=_json.dumps(response, ensure_ascii=False),
            metadata=metadata or {},
        ))

    def log_tool_call(self, session_id: int, tool_name: str, params: dict, result: Optional[dict] = None):
        """记录工具调用。"""
        import json as _json
        self.append_log(LogEntry(
            session_id=session_id,
            action="tool_call",
            content=_json.dumps({"tool": tool_name, "params": params, "result": result}, ensure_ascii=False),
            metadata={},
        ))

    def log_llm_call(self, session_id: int, model: str, prompt_tokens: int, completion_tokens: int,
                     content: str = "", metadata: Optional[dict] = None):
        """
        记录 LLM 调用及其 Token 消耗。
        这是 "Token 吐出记录" 的核心方法——每次模型调用都追加一行。
        """
        self.append_log(LogEntry(
            session_id=session_id,
            action="llm_call",
            content=content,
            metadata=metadata or {},
            token_usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                model=model,
            ),
        ))

    def log_context_prune(self, session_id: int, before_tokens: int, after_tokens: int,
                          strategy: str = "head_tail"):
        """记录上下文裁剪事件（Context Rot 防御）。"""
        self.append_log(LogEntry(
            session_id=session_id,
            action="context_prune",
            content=f"Pruned {before_tokens - after_tokens} tokens ({strategy})",
            metadata={"before_tokens": before_tokens, "after_tokens": after_tokens, "strategy": strategy},
        ))

    def get_token_summary(self, session_id: int) -> dict:
        """统计会话级别的 Token 消耗总量。"""
        entries = self.read_log(session_id, limit=10000)
        llm_calls = [e for e in entries if e.action == "llm_call"]
        return {
            "session_id": session_id,
            "llm_calls": len(llm_calls),
            "total_prompt_tokens": sum(e.token_usage.prompt_tokens for e in llm_calls if e.token_usage),
            "total_completion_tokens": sum(e.token_usage.completion_tokens for e in llm_calls if e.token_usage),
            "total_tokens": sum(e.token_count() for e in llm_calls),
            "log_entries": len(entries),
        }
