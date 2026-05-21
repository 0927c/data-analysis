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
        if tool.name == "complaint_query":
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
    if "产品线" in msg or "product" in msg:
        return "product_line_distribution"
    if "原因" in msg and ("分布" in msg or "占比" in msg or "pie" in msg):
        return "root_cause_distribution"
    if "top" in msg or "排名" in msg or "bad" in msg:
        return "defect_top15"
    if "交叉" in msg or "cross" in msg:
        return "cross_table"
    if "客户" in msg or "customer" in msg:
        return "key_customers"
    if "制造" in msg or "mfg" in msg:
        return "mfg_defect_breakdown"
    if "研发" in msg or "rnd" in msg:
        return "rnd_defect_breakdown"
    if "洞察" in msg or "insight" in msg or "建议" in msg:
        return "insights"
    if "kpi" in msg or "汇总" in msg or "summary" in msg:
        return "summary_kpis"
    return "summary_kpis"


def _infer_chart_type(message: str) -> str:
    """从用户消息推断图表类型。"""
    msg = message.lower()
    if "分布" in msg and ("原因" in msg or "cause" in msg):
        return "pie"
    if "产品线" in msg or "product" in msg:
        return "horizontal_bar"
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
        "product_line_distribution": "以下是各产品线投诉分布情况：",
        "root_cause_distribution": "以下是原因大类分布情况：",
        "defect_top15": "以下是不良类型 TOP15 排名：",
        "cross_table": "以下是产品线×原因交叉分析：",
        "key_customers": "以下是大客户投诉排名：",
        "mfg_defect_breakdown": "以下是制造原因细分：",
        "rnd_defect_breakdown": "以下是研发原因细分：",
        "insights": "以下是数据洞察和建议：",
        "summary_kpis": "以下是 KPI 汇总：",
    }
    return messages.get(query_type, "以下是分析结果：")
