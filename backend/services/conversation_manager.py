"""多轮对话上下文管理器。"""

import json
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class ContextState:
    active_filters: dict = field(default_factory=dict)
    current_datasource: str = "complaint_data"
    last_chart_type: Optional[str] = None
    last_report_id: Optional[int] = None
    # --- 多数据源支持 ---
    primary_datasource_id: Optional[int] = None
    active_datasource_ids: List[int] = field(default_factory=list)
    # --- 记忆上下文缓存 ---
    memory_context: dict = field(default_factory=dict)

    def merge(self, new_filters: dict) -> dict:
        merged = {**self.active_filters, **new_filters}
        if new_filters.get("product_line") == "__all__":
            merged.pop("product_line", None)
        return merged

    def reset(self):
        self.active_filters = {}
        self.last_chart_type = None
        self.last_report_id = None
        # 不清除数据源和记忆上下文

    def switch_datasource(self, datasource_id: int):
        """切换到指定数据源。"""
        self.primary_datasource_id = datasource_id
        if datasource_id not in self.active_datasource_ids:
            self.active_datasource_ids.append(datasource_id)

    def add_datasource(self, datasource_id: int):
        """添加一个活跃数据源。"""
        if datasource_id not in self.active_datasource_ids:
            self.active_datasource_ids.append(datasource_id)
        if self.primary_datasource_id is None:
            self.primary_datasource_id = datasource_id

    def remove_datasource(self, datasource_id: int):
        """移除一个活跃数据源。"""
        if datasource_id in self.active_datasource_ids:
            self.active_datasource_ids.remove(datasource_id)
        if self.primary_datasource_id == datasource_id:
            self.primary_datasource_id = (
                self.active_datasource_ids[0] if self.active_datasource_ids else None
            )

    def to_json(self) -> str:
        return json.dumps({
            'active_filters': self.active_filters,
            'current_datasource': self.current_datasource,
            'last_chart_type': self.last_chart_type,
            'last_report_id': self.last_report_id,
            'primary_datasource_id': self.primary_datasource_id,
            'active_datasource_ids': self.active_datasource_ids,
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
            state.primary_datasource_id = d.get('primary_datasource_id')
            state.active_datasource_ids = d.get('active_datasource_ids', [])
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

    def switch_datasource(self, session_id: int, datasource_id: int) -> ContextState:
        """切换数据源。"""
        ctx = self.get_context(session_id)
        ctx.switch_datasource(datasource_id)
        return ctx

    def reset_context(self, session_id: int):
        ctx = self.get_context(session_id)
        ctx.reset()

    def save_state(self, session_id: int) -> str:
        return self.get_context(session_id).to_json()

    def load_state(self, session_id: int, json_data: Optional[str]):
        self._contexts[session_id] = ContextState.from_json(json_data)
