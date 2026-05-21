"""MCP 兼容工具基类。每个工具提供 name、description、parameters schema 和 execute()。"""

from abc import ABC, abstractmethod


class MCPTool(ABC):
    """统一工具接口。现有 backend 服务通过此类包装为 MCP 工具。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """工具标识，如 'complaint_query'。"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """人类可读描述，用于 Agent 选择工具。"""
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict:
        """JSON Schema 参数定义。"""
        ...

    @abstractmethod
    async def execute(self, **kwargs) -> dict:
        """执行工具，返回结构化结果。"""
        ...

    def to_spec(self) -> dict:
        """返回 MCP 兼容的工具规格。"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
