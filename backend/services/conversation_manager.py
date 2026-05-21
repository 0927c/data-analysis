"""多轮对话上下文管理器。"""

import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ContextState:
    active_filters: dict = field(default_factory=dict)
    current_datasource: str = "complaint_data"
    last_chart_type: Optional[str] = None
    last_report_id: Optional[int] = None

    def merge(self, new_filters: dict) -> dict:
        merged = {**self.active_filters, **new_filters}
        if new_filters.get("product_line") == "__all__":
            merged.pop("product_line", None)
        return merged

    def reset(self):
        self.active_filters = {}
        self.last_chart_type = None
        self.last_report_id = None

    def to_json(self) -> str:
        return json.dumps({
            'active_filters': self.active_filters,
            'current_datasource': self.current_datasource,
            'last_chart_type': self.last_chart_type,
            'last_report_id': self.last_report_id,
        }, ensure_ascii=False)

    @classmethod
    def from_json(cls, data: Optional[str]) -> 'ContextState':
        if not data:
            return cls()
        try:
            d = json.loads(data)
            state = cls()
            state.active_filters = d.get('active_filters', {})
            state.current_datasource = d.get('current_datasource', 'complaint_data')
            state.last_chart_type = d.get('last_chart_type')
            state.last_report_id = d.get('last_report_id')
            return state
        except (json.JSONDecodeError, TypeError):
            return cls()


class ConversationManager:
    """管理每个对话 session 的上下文状态。"""

    def __init__(self):
        self._contexts: dict[int, ContextState] = {}

    def get_context(self, session_id: int) -> ContextState:
        return self._contexts.setdefault(session_id, ContextState())

    def update_context(self, session_id: int, new_filters: dict) -> ContextState:
        ctx = self.get_context(session_id)
        ctx.active_filters = ctx.merge(new_filters)
        return ctx

    def update_last_report(self, session_id: int, report_id: int, chart_type: str):
        ctx = self.get_context(session_id)
        ctx.last_report_id = report_id
        ctx.last_chart_type = chart_type

    def reset_context(self, session_id: int):
        ctx = self.get_context(session_id)
        ctx.reset()

    def save_state(self, session_id: int) -> str:
        return self.get_context(session_id).to_json()

    def load_state(self, session_id: int, json_data: Optional[str]):
        self._contexts[session_id] = ContextState.from_json(json_data)
