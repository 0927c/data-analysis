"""ChartRenderTool: 包装 ChartRenderer 函数为 MCP 工具。"""

from __future__ import annotations
from internal.tools.base import MCPTool
from backend.services.chart_renderer import (
    render_pie, render_bar, render_stacked_bar,
    render_horizontal_bar, render_rose,
)


class ChartRenderTool(MCPTool):
    """
    将 chart_renderer 的 5 个渲染函数包装为统一工具接口。
    返回 ECharts option JSON，可直接用于前端渲染。
    """

    CHART_TYPES = ["pie", "bar", "stacked_bar", "horizontal_bar", "rose"]

    @property
    def name(self) -> str:
        return "chart_render"

    @property
    def description(self) -> str:
        return (
            "Render ECharts configuration from data. "
            "Supports pie, bar, stacked_bar, horizontal_bar, rose chart types. "
            "Returns dark-theme styled ECharts option JSON."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "chart_type": {
                    "type": "string",
                    "enum": self.CHART_TYPES,
                    "description": "Chart type to render",
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Data labels (for pie/bar/rose)",
                },
                "values": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Data values (for pie/bar/rose)",
                },
                "products": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Product names (for stacked_bar)",
                },
                "causes": {
                    "type": "object",
                    "description": "Cause breakdown data (for stacked_bar), format: {cause_name: [values]}",
                },
                "title": {
                    "type": "string",
                    "description": "Chart title",
                },
            },
            "required": ["chart_type"],
        }

    async def execute(
        self,
        chart_type: str,
        labels: list | None = None,
        values: list | None = None,
        products: list | None = None,
        causes: dict | None = None,
        title: str = "",
    ) -> dict:
        """Render ECharts option JSON for the given chart type."""
        renderers = {
            "pie": lambda: render_pie(labels or [], values or [], title),
            "bar": lambda: render_bar(labels or [], values or [], title),
            "stacked_bar": lambda: render_stacked_bar(products or [], causes or {}, title),
            "horizontal_bar": lambda: render_horizontal_bar(labels or [], values or [], title),
            "rose": lambda: render_rose(labels or [], values or [], title),
        }

        renderer = renderers.get(chart_type)
        if renderer is None:
            return {"error": f"Unknown chart_type: {chart_type}", "available": self.CHART_TYPES}

        try:
            option = renderer()
            return {"chart_type": chart_type, "option": option, "status": "success"}
        except Exception as e:
            return {"error": str(e), "chart_type": chart_type, "status": "error"}
