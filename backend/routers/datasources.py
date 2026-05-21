"""数据源管理路由（管理员）。"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.utils import convert_numpy

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies import get_current_user, require_admin
from backend.models import User, DataSource, Report
from backend.services.complaint_processor import ComplaintProcessor

router = APIRouter()


@router.get("")
async def get_datasources(user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """数据源列表。"""
    result = await db.execute(select(DataSource).order_by(DataSource.created_at.desc()))
    items = result.scalars().all()
    return [
        {
            'id': d.id, 'name': d.name, 'type': d.type,
            'status': d.status, 'record_count': d.record_count,
            'last_updated': d.last_updated, 'created_at': d.created_at,
        }
        for d in items
    ]


@router.put("/{ds_id}")
async def update_datasource(
    ds_id: int,
    name: Optional[str] = None,
    config: Optional[str] = None,
    field_mapping: Optional[str] = None,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """更新数据源配置。"""
    result = await db.execute(select(DataSource).where(DataSource.id == ds_id))
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    if name is not None:
        ds.name = name
    if config is not None:
        ds.config = config
    if field_mapping is not None:
        ds.field_mapping = field_mapping

    await db.commit()
    return {"message": "数据源已更新", "id": ds.id}


@router.post("/{ds_id}/refresh")
async def refresh_datasource(
    ds_id: int,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """刷新数据源（重新加载数据）。"""
    from backend.routers.analytics import get_processor

    result = await db.execute(select(DataSource).where(DataSource.id == ds_id))
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    # 重新加载处理器数据
    processor = get_processor()
    if processor:
        processor._df = None  # 清除缓存，强制重新加载
        df = processor.df
        ds.record_count = len(df)
        ds.last_updated = datetime.now(timezone.utc)
        ds.status = "active"
        await db.commit()

    return {"message": "数据源已刷新", "record_count": ds.record_count}


@router.delete("/{ds_id}")
async def delete_datasource(
    ds_id: int,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """删除数据源（有关联报表时禁止）。"""
    from backend.models import Report

    result = await db.execute(select(DataSource).where(DataSource.id == ds_id))
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    # 检查是否有关联报表
    report_count = (await db.execute(
        select(func.count()).select_from(Report).where(Report.datasource_id == ds_id)
    )).scalar()
    if report_count > 0:
        raise HTTPException(status_code=400, detail=f"该数据源有 {report_count} 个关联报表，无法删除")

    await db.delete(ds)
    await db.commit()
    return {"message": "数据源已删除"}


# ============================================================
# 文件上传：Excel → 自动解析 → 生成报表
# ============================================================
UPLOAD_DIR = Path(__file__).parent.parent / "data" / "uploads"


def _ensure_upload_dir():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _build_chart(render_func, chart_type: str, chart_id: str, title: str, *args, **kwargs) -> dict:
    """调用 chart_renderer 函数，组装为 Report 存储格式。"""
    from backend.services import chart_renderer

    option = render_func(*args, **kwargs)
    return {
        'id': chart_id,
        'title': title,
        'type': chart_type,
        'option': option,
    }


@router.post("/upload")
async def upload_excel(
    file: UploadFile = File(...),
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """上传 Excel 文件，自动解析并生成报表。"""
    # 验证文件类型
    filename = file.filename or "upload.xlsx"
    if not filename.lower().endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx / .xls 格式文件")

    _ensure_upload_dir()

    # 保存文件
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = filename.replace(' ', '_')
    upload_path = UPLOAD_DIR / f"{ts}_{safe_name}"
    with upload_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    # 解析 Excel
    from backend.services import chart_renderer

    try:
        processor = ComplaintProcessor(str(upload_path))
        _ = processor.df  # 触发加载和原因分类
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Excel 解析失败: {e}")

    total = len(processor.df)
    ds_name = Path(filename).stem

    # 创建 DataSource
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

    # 生成图表数据
    charts = []

    # 1. 产品线分布
    pl = processor.get_product_line_distribution()
    charts.append(_build_chart(
        chart_renderer.render_horizontal_bar, 'horizontal_bar',
        'product_line', '各产品线投诉量排名',
        pl['labels'], pl['values'],
    ))

    # 2. 原因大类分布
    rc = processor.get_root_cause_distribution()
    charts.append(_build_chart(
        chart_renderer.render_pie, 'pie',
        'root_cause', '投诉原因大类分布',
        rc['labels'], rc['values'],
    ))

    # 3. 二级不良 TOP15
    d15 = processor.get_defect_top15()
    charts.append(_build_chart(
        chart_renderer.render_bar, 'bar',
        'defect_top15', '二级不良类型 TOP15',
        d15['labels'], d15['values'], True,
    ))

    # 4. 产品线 × 原因交叉
    ct = processor.get_cross_table()
    charts.append(_build_chart(
        chart_renderer.render_stacked_bar, 'stacked_bar',
        'cross_table', '产品线 × 原因大类交叉分析',
        ct['products'], ct['causes'],
    ))

    # 5. 大客户投诉
    kc = processor.get_key_customers()
    if kc['labels']:
        charts.append(_build_chart(
            chart_renderer.render_horizontal_bar, 'horizontal_bar',
            'key_customers', '大客户投诉排名',
            kc['labels'], kc['values'],
        ))

    # 6-9. 各原因大类细分（玫瑰图）
    breakdowns = [
        ('mfg_breakdown', '制造原因细分', processor.get_mfg_defect_breakdown),
        ('rnd_breakdown', '研发原因细分', processor.get_rnd_defect_breakdown),
        ('cli_breakdown', '客户原因细分', processor.get_cli_defect_breakdown),
        ('wh_breakdown', '仓储原因细分', processor.get_wh_defect_breakdown),
    ]
    for cid, ctitle, func in breakdowns:
        bd = func()
        if bd['labels']:
            charts.append(_build_chart(
                chart_renderer.render_rose, 'rose',
                cid, ctitle,
                bd['labels'], bd['values'],
            ))

    # 生成洞察
    insights = processor.generate_insights()

    # 生成 KPI + 数据表
    kpis = processor.get_summary_kpis()
    data_table = _build_data_table(processor, total)

    # 创建 Report
    charts_safe = convert_numpy(charts)
    chart_config = json.dumps([
        {'id': c['id'], 'title': c['title'], 'type': c['type'], 'option': c['option']}
        for c in charts_safe
    ], ensure_ascii=False)

    report = Report(
        user_id=user.id,
        title=f'{ds_name} 自动分析报告',
        datasource_id=ds.id,
        report_type='auto_upload',
        chart_config=chart_config,
        data_payload=json.dumps(convert_numpy(data_table), ensure_ascii=False),
        insights=json.dumps(convert_numpy([i['title'] for i in insights]), ensure_ascii=False),
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    return {
        'report_id': report.id,
        'datasource_id': ds.id,
        'total_records': total,
        'filename': filename,
        'chart_count': len(charts),
        'insight_count': len(insights),
    }


def _build_data_table(processor: ComplaintProcessor, total: int) -> dict:
    """构建数据明细表（前 100 行原始数据 + 汇总行）。"""
    df = processor.df.head(100)
    headers = ['序号', '产品线', '二级不良', '提取原因', '原因大类']
    rows = []
    for i, (_, row) in enumerate(df.iterrows(), start=1):
        rows.append([
            i,
            str(row.get('产品线', '')),
            str(row.get('二级不良', '')),
            str(row.get('提取原因', '')),
            str(row.get('原因大类', '')),
        ])
    rows.append(['', '', '', '', f'合计: {total} 件 (展示前100行)'])
    return {'headers': headers, 'rows': rows}
