"""TicketQueryTool: 包装 TicketProcessor 为 MCP 工具。"""

from typing import Optional

from internal.tools.base import MCPTool


class TicketQueryTool(MCPTool):

    QUERY_TYPES = [
        "summary_kpis",
        "status_distribution",
        "service_group_distribution",
        "assignee_distribution",
        "department_distribution",
        "source_distribution",
        "source_channel_distribution",
        "fault_group_distribution",
        "cause_category_distribution",
        "business_system_distribution",
        "nature_distribution",
        "resolution_method_distribution",
        "resolver_distribution",
        "status_by_service_group",
        "weekly_trend",
        "monthly_trend",
        "sla_weekly_trend",
        "suspended_breakdown",
        "evaluation_summary",
        "resolution_time_buckets",
        "insights",
        "fault_root_cause_analysis",
        "fault_cause_trend",
        "symptom_solution_mapping",
        "recurring_tickets",
        "nature_trend",
        "requester_behavior",
        "ops_quality_metrics",
    ]

    def __init__(self, processor):
        self._processor = processor

    @property
    def name(self) -> str:
        return "ticket_query"

    @property
    def description(self) -> str:
        return (
            "Query ITSM ticket data by filters. "
            "Supports status, service group, assignee, department, source, "
            "fault grouping, SLA trends, weekly/monthly trends and more."
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
                        "status": {"type": "string"},
                        "assignee": {"type": "string"},
                        "department": {"type": "string"},
                        "service_group": {"type": "string"},
                        "source": {"type": "string"},
                        "source_channel": {"type": "string"},
                        "cause_category": {"type": "string"},
                        "fault_group": {"type": "string"},
                        "nature": {"type": "string"},
                        "date_from": {"type": "string"},
                        "date_to": {"type": "string"},
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
        method_map = {
            "summary_kpis": self._processor.get_summary_kpis,
            "status_distribution": self._processor.get_status_distribution,
            "service_group_distribution": self._processor.get_service_group_distribution,
            "assignee_distribution": lambda f: self._processor.get_assignee_distribution(f, top_n=top_n),
            "department_distribution": self._processor.get_department_distribution,
            "source_distribution": self._processor.get_source_distribution,
            "source_channel_distribution": self._processor.get_source_channel_distribution,
            "fault_group_distribution": self._processor.get_fault_group_distribution,
            "cause_category_distribution": self._processor.get_cause_category_distribution,
            "business_system_distribution": self._processor.get_business_system_distribution,
            "nature_distribution": self._processor.get_nature_distribution,
            "resolution_method_distribution": self._processor.get_resolution_method_distribution,
            "resolver_distribution": lambda f: self._processor.get_resolver_distribution(f, top_n=top_n),
            "status_by_service_group": self._processor.get_status_by_service_group,
            "weekly_trend": self._processor.get_weekly_trend,
            "monthly_trend": self._processor.get_monthly_trend,
            "sla_weekly_trend": self._processor.get_sla_weekly_trend,
            "suspended_breakdown": self._processor.get_suspended_breakdown,
            "evaluation_summary": self._processor.get_evaluation_summary,
            "resolution_time_buckets": self._processor.get_resolution_time_buckets,
            "insights": self._processor.generate_insights,
            "fault_root_cause_analysis": self._processor.get_fault_root_cause_analysis,
            "fault_cause_trend": lambda f: self._processor.get_fault_cause_trend(f, top_n=top_n),
            "symptom_solution_mapping": self._processor.get_symptom_solution_mapping,
            "recurring_tickets": self._processor.get_recurring_tickets,
            "nature_trend": self._processor.get_nature_trend,
            "requester_behavior": self._processor.get_requester_behavior,
            "ops_quality_metrics": self._processor.get_ops_quality_metrics,
        }

        method = method_map.get(query_type)
        if method is None:
            return {"error": f"Unknown query_type: {query_type}", "available": self.QUERY_TYPES}

        try:
            result = method(filters or {})
            return {"query_type": query_type, "data": result, "status": "success"}
        except Exception as e:
            return {"error": str(e), "query_type": query_type, "status": "error"}
