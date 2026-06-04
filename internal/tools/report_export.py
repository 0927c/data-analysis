"""ReportExportTool: 包装 ExportService 为 MCP 工具。"""

from __future__ import annotations
from internal.tools.base import MCPTool
from backend.services.export_service import export_html, export_excel


class ReportExportTool(MCPTool):
    """
    将 export_service 的导出函数包装为统一工具接口。
    支持 HTML（Jinja2 模板）和 Excel（openpyxl）两种格式。
    """

    FORMATS = ["html", "excel"]

    def __init__(self, processor):
        self._processor = processor

    @property
    def name(self) -> str:
        return "report_export"

    @property
    def description(self) -> str:
        return (
            "Export report as HTML or Excel format. "
            "HTML: standalone page with dark theme and embedded ECharts. "
            "Excel: workbook with data, KPI summary, and insights sheets."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "enum": self.FORMATS,
                    "description": "Export format: html or excel",
                },
                "title": {
                    "type": "string",
                    "description": "Report title",
                },
                "charts": {
                    "type": "array",
                    "description": "Chart data: [{id, title, option}]",
                },
                "insights": {
                    "type": "array",
                    "description": "Insight items: [{severity, title, desc}]",
                },
                "data_table": {
                    "type": "object",
                    "description": "Data table: {headers: [...], rows: [[...]]}",
                },
            },
            "required": ["format", "title"],
        }

    async def execute(
        self,
        format: str,
        title: str,
        charts: list | None = None,
        insights: list | None = None,
        data_table: dict | None = None,
    ) -> dict:
        """Export report and return content (or metadata for large payloads)."""
        charts = charts or []
        insights = insights or []
        data_table = data_table or {}

        try:
            if format == "html":
                kpis = self._processor.get_summary_kpis()
                content = export_html(
                    title=title,
                    charts=charts,
                    insights=insights,
                    data_table=data_table,
                    total=kpis.get("total", 0),
                )
                return {
                    "format": "html",
                    "content_length": len(content),
                    "status": "success",
                }
            elif format == "excel":
                kpis = self._processor.get_summary_kpis()
                content = export_excel(
                    title=title,
                    data_table=data_table,
                    kpis=kpis,
                    insights=insights,
                )
                return {
                    "format": "excel",
                    "content_length": len(content),
                    "status": "success",
                }
            else:
                return {"error": f"Unknown format: {format}", "available": self.FORMATS}
        except Exception as e:
            return {"error": str(e), "format": format, "status": "error"}
