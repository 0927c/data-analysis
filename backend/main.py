"""FastAPI 应用入口。"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.database import engine, Base, get_db
from backend.auth import get_current_user
from backend.models import User
from backend.services.ticket_processor import TicketProcessor
from backend.services.conversation_manager import ConversationManager
from backend.services.intent_parser import IntentParser
from backend.services.skill_engine import SkillEngine
from backend.routers import auth, chat, reports, datasources, skills, analytics
from backend.routers.chat import set_globals as set_chat_globals
from backend.routers.analytics import set_processor as set_analytics_processor
from backend.routers.reports import set_processor as set_reports_processor


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化
    Path("backend/data").mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 初始化服务
    processor = None
    if settings.TICKET_EXCEL_PATH:
        try:
            processor = TicketProcessor(settings.TICKET_EXCEL_PATH)
            _ = processor.df
        except FileNotFoundError:
            print(f"Warning: Excel 文件不存在: {settings.TICKET_EXCEL_PATH}，数据分析功能不可用")
        except Exception as e:
            print(f"Warning: 加载 Excel 失败: {e}，数据分析功能不可用")
    else:
        print("Warning: TICKET_EXCEL_PATH 未配置，数据分析功能不可用")

    conversation_manager = ConversationManager()

    # 创建 LLM Provider
    llm_provider = None
    if settings.LLM_API_KEY:
        try:
            from backend.llm.base import create_llm_provider
            kwargs = {
                'api_key': settings.LLM_API_KEY,
                'model': settings.LLM_MODEL,
            }
            if settings.LLM_BASE_URL:
                kwargs['base_url'] = settings.LLM_BASE_URL
            llm_provider = create_llm_provider(settings.LLM_PROVIDER, **kwargs)
            print(f"✓ LLM Provider 已初始化: {settings.LLM_PROVIDER} / {settings.LLM_MODEL}")
        except Exception as e:
            print(f"Warning: LLM Provider 初始化失败: {e}，使用规则引擎兜底")
            llm_provider = None

    # 启动 Flue Agent 子进程（如果启用）
    flue_agent_process = None
    if settings.FLUE_AGENT_ENABLED:
        try:
            import subprocess
            flue_agent_dir = Path(__file__).parent.parent / "flue-agent"
            flue_agent_process = subprocess.Popen(
                ["node", "agent-server.js"],
                cwd=str(flue_agent_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print(f"✓ Flue Agent 子进程已启动 (PID: {flue_agent_process.pid})")
        except Exception as e:
            print(f"Warning: Flue Agent 启动失败: {e}")

    intent_parser = IntentParser(llm_provider=llm_provider)
    skill_engine = SkillEngine(processor, llm_provider=llm_provider)

    # 注入到路由
    set_chat_globals(conversation_manager, intent_parser, skill_engine, processor)
    set_analytics_processor(processor)
    set_reports_processor(processor)

    # ─── Harness 层初始化 ───────────────────────────────
    from internal.session.manager import SessionManager
    from internal.context.manager import ContextManager as HarnessContextManager
    from internal.memory.store import MemoryStore
    from internal.router.agent_registry import AgentRegistry
    from internal.router.skill_router import SkillRouter
    from internal.tools.ticket_query import TicketQueryTool
    from internal.tools.chart_render import ChartRenderTool
    from internal.tools.report_export import ReportExportTool
    from internal.router import harness_router

    from backend.database import async_session

    session_mgr = SessionManager(async_session)
    harness_ctx = HarnessContextManager(conversation_manager, max_tokens=8000)
    memory = MemoryStore()

    registry = AgentRegistry(agents_dir=Path(".claude/agents"))
    registry.load_all()

    tools = [
        TicketQueryTool(processor),
        ChartRenderTool(),
        ReportExportTool(processor),
    ]
    skill_router = SkillRouter(registry, tools)

    # 存储到 app.state
    app.state.session_manager = session_mgr
    app.state.harness_context = harness_ctx
    app.state.memory = memory
    app.state.skill_router = skill_router
    app.state.agent_registry = registry

    # 挂载 harness router
    app.include_router(harness_router, prefix="/api/harness", tags=["Harness"])
    # ─────────────────────────────────────────────────────

    yield

    # 清理 Flue Agent 子进程
    if flue_agent_process:
        try:
            flue_agent_process.terminate()
            flue_agent_process.wait(timeout=5)
            print("✓ Flue Agent 子进程已终止")
        except Exception:
            try:
                flue_agent_process.kill()
            except Exception:
                pass


app = FastAPI(
    title="智能报表分析 Agent 平台",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in getattr(settings, 'CORS_ORIGINS', 'http://localhost:3000').split(',')],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由注册
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(chat.router, prefix="/api/chat", tags=["Agent 对话"])
app.include_router(reports.router, prefix="/api/reports", tags=["报表管理"])
app.include_router(datasources.router, prefix="/api/datasources", tags=["数据源管理"])
app.include_router(skills.router, prefix="/api/skills", tags=["Skill 管理"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["数据分析"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
