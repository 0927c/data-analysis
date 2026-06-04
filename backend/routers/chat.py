"""Agent 对话路由。"""

from __future__ import annotations
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models import User, Session, Message, Report, DataSource
from backend.schemas import (
    ChatMessageRequest, ChatResponse, ChartData,
    SessionOut, MessageOut,
)
from backend.services.ticket_processor import TicketProcessor
from backend.services.conversation_manager import ConversationManager
from backend.services.intent_parser import IntentParser
from backend.services.skill_engine import SkillEngine
from backend.services.report_generator import assemble_report

from backend.utils import convert_numpy

UPLOAD_DIR = Path(__file__).parent.parent / "data" / "uploads"

router = APIRouter()

# Global instances (set in main.py)
_conversation_manager: Optional[ConversationManager] = None
_intent_parser: Optional[IntentParser] = None
_skill_engine: Optional[SkillEngine] = None
_processor: Optional[TicketProcessor] = None


def get_cm() -> ConversationManager:
    return _conversation_manager


def get_ip() -> IntentParser:
    return _intent_parser


def get_se() -> SkillEngine:
    return _skill_engine


def get_cp() -> TicketProcessor:
    return _processor


def set_globals(cm: ConversationManager, ip: IntentParser, se: SkillEngine, cp: TicketProcessor):
    global _conversation_manager, _intent_parser, _skill_engine, _processor
    _conversation_manager = cm
    _intent_parser = ip
    _skill_engine = se
    _processor = cp


@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatMessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """发送消息，获取 Agent 响应。"""
    cm = get_cm()
    ip = get_ip()
    se = get_se()

    # 获取或创建 session
    session_id = req.session_id
    if session_id is None:
        session = Session(user_id=user.id, title=req.message[:50])
        db.add(session)
        await db.flush()
        session_id = session.id
    else:
        # 验证 session 归属
        result = await db.execute(select(Session).where(Session.id == session_id, Session.user_id == user.id))
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")

    # 保存用户消息
    user_msg = Message(session_id=session_id, role="user", content=req.message)
    db.add(user_msg)
    await db.flush()

    # 加载上下文
    cm.load_state(session_id, session.context_state)
    ctx = cm.get_context(session_id)

    # 检查重置命令
    try:
        intent = await ip.parse(req.message, ctx, se.get_available_skills())
    except Exception:
        intent = ip._parse_with_rules(req.message, ctx)
    if intent.get('action') == 'reset_context':
        cm.reset_context(session_id)
        ctx = cm.get_context(session_id)
        intent = await ip.parse(req.message, ctx, se.get_available_skills())

    # 更新上下文
    if intent.get('filters'):
        ctx = cm.update_context(session_id, intent['filters'])

    # 执行 skill
    intent['message'] = req.message
    history_result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id, Message.id < user_msg.id)
        .order_by(Message.id.desc())
        .limit(6)
    )
    recent_msgs = list(reversed(history_result.scalars().all()))
    intent['chat_history'] = [
        {'role': m.role, 'content': m.content}
        for m in recent_msgs if m.content
    ]
    try:
        result = await se.execute_skill(intent.get('skill_id', 'ticket_analysis'), intent)
    except ValueError as e:
        agent_msg = Message(session_id=session_id, role="assistant", content=str(e))
        db.add(agent_msg)
        await db.commit()
        return ChatResponse(message=str(e), session_id=session_id)
    except Exception as e:
        agent_msg = Message(session_id=session_id, role="assistant", content=f"抱歉，处理你的请求时遇到了问题，请稍后再试。")
        db.add(agent_msg)
        await db.commit()
        return ChatResponse(message=agent_msg.content, session_id=session_id)

    # 闲聊分支：不需要生成报表
    is_chitchat = intent.get('action') == 'chitchat' or intent.get('skill_id') == 'chitchat'
    agent_content = result.get('message', '报表已生成')

    if is_chitchat:
        agent_msg = Message(
            session_id=session_id,
            role='assistant',
            content=agent_content,
        )
        db.add(agent_msg)
        session.context_state = cm.save_state(session_id)
        session.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return ChatResponse(message=agent_content, session_id=session_id)

    # 工单分析分支：生成报表
    report_data = assemble_report(
        title=req.message[:100],
        charts=result['charts'],
        insights=result['insights'],
        data_table=result.get('data_table'),
    )
    report = Report(
        user_id=user.id,
        session_id=session_id,
        title=req.message[:100],
        report_type=report_data['report_type'],
        chart_config=report_data['chart_config'],
        data_payload=report_data['data_payload'],
        insights=report_data['insights'],
    )
    db.add(report)
    await db.flush()
    report_id = report.id

    # 更新上下文中的最后报告 ID
    chart_type = result['charts'][0]['type'] if result['charts'] else None
    cm.update_last_report(session_id, report_id, chart_type or '')

    # 保存 Agent 响应
    agent_content = result.get('message', '报表已生成')
    agent_msg = Message(
        session_id=session_id,
        role='assistant',
        content=agent_content,
        has_report=True,
        report_id=report_id,
    )
    db.add(agent_msg)

    # 保存会话上下文
    session.context_state = cm.save_state(session_id)
    session.updated_at = datetime.now(timezone.utc)

    await db.commit()

    charts = [
        ChartData(id=c['id'], title=c['title'], type=c['type'], option=c['option'])
        for c in convert_numpy(result['charts'])
    ]

    return ChatResponse(
        message=agent_content,
        session_id=session_id,
        charts=charts,
        insights=convert_numpy([i.get('title', '') for i in result.get('insights', [])]),
        data_table=convert_numpy(result.get('data_table')),
        report_id=report_id,
    )


@router.post("/upload", response_model=ChatResponse)
async def chat_with_upload(
    file: UploadFile = File(...),
    message: str = Form('请帮我分析这个文件的数据'),
    session_id: Optional[int] = Form(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """带附件的聊天接口：上传 Excel → 解析 → 更新全局 processor → 生成报表 → 返回对话响应。"""
    filename = file.filename or "upload.xlsx"
    if not filename.lower().endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx / .xls 格式文件")

    # 保存上传文件
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = filename.replace(' ', '_')
    upload_path = UPLOAD_DIR / f"{ts}_{safe_name}"
    with upload_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    # 解析 Excel，创建新 processor
    try:
        new_processor = TicketProcessor(str(upload_path))
        _ = new_processor.df  # 触发加载
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Excel 解析失败: {e}")

    # 更新全局 processor（让后续对话也能用新数据）
    global _processor
    _processor = new_processor
    get_se().processor = new_processor

    # 同步更新 analytics / reports 的 processor
    from backend.routers.analytics import set_processor as set_analytics_processor
    from backend.routers.reports import set_processor as set_reports_processor
    set_analytics_processor(new_processor)
    set_reports_processor(new_processor)

    total = len(new_processor.df)
    ds_name = Path(filename).stem

    # 创建 DataSource 记录
    ds = DataSource(
        name=ds_name,
        type='excel',
        config=json.dumps({'uploaded_path': str(upload_path)}, ensure_ascii=False),
        status='active',
        record_count=total,
        last_updated=datetime.now(timezone.utc),
    )
    db.add(ds)
    await db.flush()

    # 获取或创建 session
    cm = get_cm()
    if session_id is None:
        session = Session(user_id=user.id, title=f"{ds_name} 数据分析")
        db.add(session)
        await db.flush()
        session_id = session.id
    else:
        result_q = await db.execute(select(Session).where(Session.id == session_id, Session.user_id == user.id))
        session = result_q.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")

    # 保存用户消息
    user_msg = Message(session_id=session_id, role="user", content=f"[上传文件] {filename}\n{message}")
    db.add(user_msg)

    # 上传后生成完整分析报表
    from backend.services import chart_renderer

    charts = []

    if 'status' in new_processor.df.columns:
        sd = new_processor.get_status_distribution()
        charts.append({
            'id': 'status',
            'title': '工单状态分布',
            'type': 'pie',
            'option': chart_renderer.render_pie(sd['labels'], sd['values']),
        })

    if 'service_group' in new_processor.df.columns:
        sg = new_processor.get_service_group_distribution()
        charts.append({
            'id': 'service_group',
            'title': '服务组工单量排名',
            'type': 'horizontal_bar',
            'option': chart_renderer.render_horizontal_bar(sg['labels'], sg['values']),
        })

    if 'business_system' in new_processor.df.columns:
        bs = new_processor.get_business_system_distribution()
        charts.append({
            'id': 'business_system',
            'title': '业务系统分布',
            'type': 'horizontal_bar',
            'option': chart_renderer.render_horizontal_bar(bs['labels'], bs['values']),
        })

    if 'fault_group' in new_processor.df.columns:
        fg = new_processor.get_fault_group_distribution()
        charts.append({
            'id': 'fault_group',
            'title': '故障原因分组',
            'type': 'pie',
            'option': chart_renderer.render_pie(fg['labels'], fg['values']),
        })

    if 'created_week' in new_processor.df.columns:
        wt = new_processor.get_weekly_trend()
        charts.append({
            'id': 'weekly_trend',
            'title': '每周工单趋势',
            'type': 'line',
            'option': chart_renderer.render_line(wt['labels'], [{'name': '工单数', 'data': wt['values']}]),
        })

    if 'assignee' in new_processor.df.columns:
        ad = new_processor.get_assignee_distribution()
        charts.append({
            'id': 'assignee',
            'title': '责任人处理量 TOP15',
            'type': 'horizontal_bar',
            'option': chart_renderer.render_horizontal_bar(ad['labels'], ad['values']),
        })

    # 洞察 + KPI + 数据表
    insights = new_processor.get_summary_kpis()
    kpis = insights

    df_top = new_processor.df.head(100)
    data_table = {
        'headers': ['序号', '标题', '状态', '请求人', '责任人', '服务组', '创建时间'],
        'rows': [
            [i, str(r.get('title', '')), str(r.get('status', '')), str(r.get('requester', '')), str(r.get('responsible_person', '')), str(r.get('service_group', '')), str(r.get('created_at', ''))]
            for i, (_, r) in enumerate(df_top.iterrows(), start=1)
        ] + [['', '', '', '', '', '', f'合计: {total} 件 (展示前100行)']],
    }

    result = {
        'message': f'已上传 {filename}（共 {total} 条记录），完成全面分析：',
        'charts': charts,
        'insights': insights,
        'data_table': data_table,
    }

    # 保存报表
    report_data = assemble_report(
        title=f"{ds_name} 自动分析报告",
        charts=result['charts'],
        insights=result['insights'],
        data_table=result.get('data_table'),
    )
    report = Report(
        user_id=user.id,
        session_id=session_id,
        datasource_id=ds.id,
        title=f"{ds_name} 自动分析报告",
        report_type=report_data['report_type'],
        chart_config=report_data['chart_config'],
        data_payload=report_data['data_payload'],
        insights=report_data['insights'],
    )
    db.add(report)
    await db.flush()
    report_id = report.id

    # 保存 Agent 响应
    agent_content = result.get('message', '报表已生成')
    agent_msg = Message(
        session_id=session_id,
        role='assistant',
        content=agent_content,
        has_report=True,
        report_id=report_id,
    )
    db.add(agent_msg)

    # 更新上下文
    cm.load_state(session_id, session.context_state)
    cm.update_last_report(session_id, report_id, charts[0]['type'] if charts else '')
    session.context_state = cm.save_state(session_id)
    session.updated_at = datetime.now(timezone.utc)

    await db.commit()

    chart_data = [
        ChartData(id=c['id'], title=c['title'], type=c['type'], option=c['option'])
        for c in convert_numpy(result['charts'])
    ]

    return ChatResponse(
        message=agent_content,
        session_id=session_id,
        charts=chart_data,
        insights=convert_numpy([i.get('title', '') for i in result.get('insights', [])]),
        data_table=convert_numpy(result.get('data_table')),
        report_id=report_id,
    )


@router.get("/sessions", response_model=List[SessionOut])
async def get_sessions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """获取用户会话列表。"""
    result = await db.execute(
        select(Session)
        .where(Session.user_id == user.id)
        .order_by(Session.updated_at.desc())
    )
    return result.scalars().all()


@router.get("/sessions/{session_id}/messages", response_model=List[MessageOut])
async def get_messages(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取会话消息历史。"""
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="会话不存在")

    result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    )
    return result.scalars().all()


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除会话及其关联的消息和报表。"""
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 先删除关联的 messages
    msg_result = await db.execute(
        select(Message).where(Message.session_id == session_id)
    )
    for msg in msg_result.scalars().all():
        await db.delete(msg)

    # 再删除关联的 reports
    report_result = await db.execute(
        select(Report).where(Report.session_id == session_id)
    )
    for report in report_result.scalars().all():
        await db.delete(report)

    # 最后删除 session
    await db.delete(session)
    await db.commit()
    return {"message": "会话已删除"}


@router.post("/sessions/{session_id}/reset")
async def reset_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """重置会话上下文。"""
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    cm = get_cm()
    cm.reset_context(session_id)
    session.context_state = cm.save_state(session_id)
    await db.commit()
    return {"message": "对话上下文已重置"}
