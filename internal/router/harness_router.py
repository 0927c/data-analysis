"""harness_router: 新 FastAPI router，提供 harness 层 API 端点。"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from backend.dependencies import get_current_user
from backend.models import User

router = APIRouter()


# ─── Request/Response Schemas ─────────────────────────────────────

class HarnessChatRequest(BaseModel):
    message: str
    session_id: Optional[int] = None


class HarnessChatResponse(BaseModel):
    message: str
    agent_id: str
    charts: list = []
    insights: list = []
    data_table: Optional[dict] = None


class ToolExecuteRequest(BaseModel):
    params: dict = {}


class MemorySetRequest(BaseModel):
    value: str
    metadata: Optional[dict] = None


def _get_harness_state(request: Request) -> dict:
    """从 request.app.state 获取 harness 组件。"""
    return {
        "skill_router": getattr(request.app.state, "skill_router", None),
        "session_manager": getattr(request.app.state, "session_manager", None),
        "harness_context": getattr(request.app.state, "harness_context", None),
        "memory": getattr(request.app.state, "memory", None),
        "agent_registry": getattr(request.app.state, "agent_registry", None),
    }


# ─── Endpoints ─────────────────────────────────────────────────────

@router.post("/chat", response_model=HarnessChatResponse)
async def harness_chat(
    req: HarnessChatRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    """
    Harness 感知对话端点。
    流程: 关键词路由 → Agent 选择 → 工具执行 → 组装响应。
    """
    state = _get_harness_state(request)
    skill_router = state["skill_router"]
    if skill_router is None:
        raise HTTPException(status_code=500, detail="Harness not initialized")

    # Route to agent
    routing = skill_router.route(req.message)
    agent_id = routing["agent_id"]
    tools = routing["allowed_tools"]

    # Execute tools
    charts = []
    insights = []
    data_table = None
    response_message = ""

    for tool in tools:
        if tool.name == "ticket_query":
            query_type = _infer_query_type(req.message)
            result = await tool.execute(query_type=query_type)
            if result.get("status") == "success":
                response_message = _generate_response_message(query_type, result["data"])
                data_table = result["data"].get("data_table")
                insights = result["data"].get("insights", [])

        elif tool.name == "chart_render":
            chart_type = _infer_chart_type(req.message)
            result = await tool.execute(
                chart_type=chart_type,
                labels=[],
                values=[],
                title=req.message[:30],
            )
            if result.get("status") == "success":
                charts.append({
                    "title": req.message[:30],
                    "option": result.get("option", {}),
                })

    return HarnessChatResponse(
        message=response_message or "已为您生成分析报告。",
        agent_id=agent_id,
        charts=charts,
        insights=insights,
        data_table=data_table,
    )


@router.get("/agents")
async def list_agents(request: Request, user: User = Depends(get_current_user)):
    """列出所有注册的 Agent。"""
    state = _get_harness_state(request)
    registry = state["agent_registry"]
    if registry is None:
        return {"agents": []}

    agents = registry.get_all_agents()
    return {
        "agents": [
            {
                "id": a.id,
                "name": a.name,
                "description": a.description,
                "role": a.role,
                "capabilities": a.capabilities,
                "enabled": a.enabled,
            }
            for a in agents
        ]
    }


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, request: Request, user: User = Depends(get_current_user)):
    """获取指定 Agent 定义。"""
    state = _get_harness_state(request)
    registry = state["agent_registry"]
    if registry is None:
        raise HTTPException(status_code=500, detail="Harness not initialized")

    agent = registry.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    return {
        "id": agent.id,
        "name": agent.name,
        "description": agent.description,
        "role": agent.role,
        "capabilities": agent.capabilities,
        "allowed_tools": agent.allowed_tools,
        "routing_keywords": agent.routing_keywords,
        "system_prompt": agent.system_prompt,
        "enabled": agent.enabled,
    }


@router.get("/tools")
async def list_tools(request: Request, user: User = Depends(get_current_user)):
    """列出所有可用 MCP 工具。"""
    state = _get_harness_state(request)
    skill_router = state["skill_router"]
    if skill_router is None:
        return {"tools": []}

    tools = skill_router.get_all_tools()
    return {"tools": [t.to_spec() for t in tools]}


@router.post("/tools/{tool_name}")
async def execute_tool(tool_name: str, req: ToolExecuteRequest, request: Request, user: User = Depends(get_current_user)):
    """直接执行工具。"""
    state = _get_harness_state(request)
    skill_router = state["skill_router"]
    if skill_router is None:
        raise HTTPException(status_code=500, detail="Harness not initialized")

    tool = skill_router.get_tool(tool_name)
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")

    result = await tool.execute(**req.params)
    return result


@router.get("/sessions/{session_id}/log")
async def read_session_log(request: Request, session_id: int, limit: int = 100, user: User = Depends(get_current_user)):
    """读取会话 append-only 日志。"""
    state = _get_harness_state(request)
    session_manager = state["session_manager"]
    if session_manager is None:
        raise HTTPException(status_code=500, detail="Harness not initialized")

    entries = session_manager.read_log(session_id, limit=limit)
    return {
        "session_id": session_id,
        "entries": [e.to_dict() for e in entries],
        "total": len(entries),
    }


@router.get("/memory/{key}")
async def get_memory(key: str, request: Request, user: User = Depends(get_current_user)):
    """获取记忆值。"""
    state = _get_harness_state(request)
    memory = state["memory"]
    if memory is None:
        raise HTTPException(status_code=500, detail="Harness not initialized")

    value = memory.get(key)
    if value is None:
        raise HTTPException(status_code=404, detail=f"Key not found: {key}")

    return {"key": key, "value": value}


@router.put("/memory/{key}")
async def set_memory(key: str, req: MemorySetRequest, request: Request, user: User = Depends(get_current_user)):
    """设置记忆值。"""
    state = _get_harness_state(request)
    memory = state["memory"]
    if memory is None:
        raise HTTPException(status_code=500, detail="Harness not initialized")

    memory.set(key, req.value, req.metadata)
    return {"key": key, "status": "saved"}


# ─── Helper Functions ─────────────────────────────────────────────

def _infer_query_type(message: str) -> str:
    """从用户消息推断查询类型。"""
    msg = message.lower()
    if "状态" in msg:
        return "status_distribution"
    if "服务组" in msg:
        return "service_group_distribution"
    if "责任人" in msg or "处理人" in msg:
        return "assignee_distribution"
    if "部门" in msg:
        return "department_distribution"
    if "来源" in msg or "渠道" in msg:
        return "source_channel_distribution"
    if "故障" in msg:
        return "fault_group_distribution"
    if "趋势" in msg or "周报" in msg or "weekly" in msg:
        return "weekly_trend"
    if "月报" in msg or "monthly" in msg:
        return "monthly_trend"
    if "sla" in msg or "达标率" in msg or "时效" in msg:
        return "sla_weekly_trend"
    if "挂起" in msg:
        return "suspended_breakdown"
    if "评价" in msg or "满意度" in msg:
        return "evaluation_summary"
    if "根因" in msg or "根本原因" in msg or "深层" in msg:
        return "fault_root_cause_analysis"
    if "重复" in msg or "高频" in msg or "反复" in msg or "同类" in msg:
        return "recurring_tickets"
    if "症状" in msg or "方案" in msg or "聚类" in msg:
        return "symptom_solution_mapping"
    if "占比" in msg or "性质" in msg:
        return "nature_trend"
    if "请求人" in msg or "谁提交" in msg or "组织" in msg:
        return "requester_behavior"
    if "运维质量" in msg or "退回率" in msg or "撤单率" in msg:
        return "ops_quality_metrics"
    if "洞察" in msg or "insight" in msg or "建议" in msg:
        return "insights"
    if "kpi" in msg or "汇总" in msg or "summary" in msg:
        return "summary_kpis"
    return "summary_kpis"


def _infer_chart_type(message: str) -> str:
    """从用户消息推断图表类型。"""
    msg = message.lower()
    if "趋势" in msg or "tren" in msg or "走势" in msg:
        return "line"
    if "分布" in msg or "占比" in msg or "pie" in msg:
        return "pie"
    if "排名" in msg or "top" in msg:
        return "bar"
    if "交叉" in msg or "cross" in msg:
        return "stacked_bar"
    if "细分" in msg or "breakdown" in msg:
        return "rose"
    return "bar"


def _generate_response_message(query_type: str, data: dict) -> str:
    """生成人类可读的响应消息。"""
    messages = {
        "status_distribution": "以下是工单状态分布情况：",
        "service_group_distribution": "以下是服务组工作量分布：",
        "assignee_distribution": "以下是责任人处理量排名：",
        "department_distribution": "以下是请求部门分布：",
        "source_channel_distribution": "以下是来源渠道分布：",
        "fault_group_distribution": "以下是故障原因分组：",
        "weekly_trend": "以下是每周工单趋势：",
        "monthly_trend": "以下是每月工单趋势：",
        "sla_weekly_trend": "以下是 SLA 趋势：",
        "suspended_breakdown": "以下是挂起原因分析：",
        "evaluation_summary": "以下是满意度评价摘要：",
        "fault_root_cause_analysis": "以下是故障根因深度分析：",
        "fault_cause_trend": "以下是故障原因趋势分析：",
        "symptom_solution_mapping": "以下是症状→解决方案聚类：",
        "recurring_tickets": "以下是重复工单挖掘结果：",
        "nature_trend": "以下是各类性质占比与趋势：",
        "requester_behavior": "以下是请求人行为与组织分析：",
        "ops_quality_metrics": "以下是运维质量指标分析：",
        "insights": "以下是数据洞察和建议：",
        "summary_kpis": "以下是 KPI 汇总：",
    }
    return messages.get(query_type, "以下是分析结果：")
