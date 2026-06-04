"""ComplaintQueryTool: 包装 ComplaintProcessor 为 MCP 工具。"""

from __future__ import annotations
from typing import Optional

from internal.tools.base import MCPTool


class ComplaintQueryTool(MCPTool):
    """
    将 ComplaintProcessor 的 11 个分析方法包装为统一工具接口。
    支持 filters 参数进行动态筛选。
    """

    QUERY_TYPES = [
        "product_line_distribution", "root_cause_distribution",
        "defect_top15", "cross_table", "key_customers",
        "mfg_defect_breakdown", "rnd_defect_breakdown",
        "cli_defect_breakdown", "wh_defect_breakdown",
        "summary_kpis", "insights",
    ]

    def __init__(self, processor):
        self._processor = processor

    @property
    def name(self) -> str:
        return "complaint_query"

    @property
    def description(self) -> str:
        return (
            "Query complaint data by filters. "
            "Supports product line, cause category, defect type filtering. "
            "Returns distribution data ready for chart rendering."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": self.QUERY_TYPES,
                    "description": "Type of query to execute",
                },
                "filters": {
                    "type": "object",
                    "properties": {
                        "product_line": {"type": "string"},
                        "cause_category": {"type": "string"},
                        "defect_type": {"type": "string"},
                        "customer": {"type": "string"},
                    },
                    "description": "Filter conditions (optional)",
                },
                "top_n": {
                    "type": "integer",
                    "default": 15,
                    "description": "Top N results for ranking queries",
                },
            },
            "required": ["query_type"],
        }

    async def execute(
        self,
        query_type: str,
        filters: Optional[dict] = None,
        top_n: int = 15,
    ) -> dict:
        """Execute the query and return structured data."""
        method_map = {
            "product_line_distribution": self._processor.get_product_line_distribution,
            "root_cause_distribution": self._processor.get_root_cause_distribution,
            "defect_top15": lambda f: self._processor.get_defect_top15(f, top_n=top_n),
            "cross_table": self._processor.get_cross_table,
            "key_customers": lambda f: self._processor.get_key_customers(f, top_n=top_n),
            "mfg_defect_breakdown": self._processor.get_mfg_defect_breakdown,
            "rnd_defect_breakdown": self._processor.get_rnd_defect_breakdown,
            "cli_defect_breakdown": self._processor.get_cli_defect_breakdown,
            "wh_defect_breakdown": self._processor.get_wh_defect_breakdown,
            "summary_kpis": self._processor.get_summary_kpis,
            "insights": self._processor.generate_insights,
        }

        method = method_map.get(query_type)
        if method is None:
            return {"error": f"Unknown query_type: {query_type}", "available": self.QUERY_TYPES}

        try:
            result = method(filters or {})
            return {"query_type": query_type, "data": result, "status": "success"}
        except Exception as e:
            return {"error": str(e), "query_type": query_type, "status": "error"}
