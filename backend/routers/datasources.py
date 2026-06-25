"""数据源管理路由（管理员）。"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Tuple

import pandas as pd
from backend.utils import convert_numpy

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies import get_current_user, require_admin
from backend.models import User, DataSource, Report
from backend.services.ticket_processor import TicketProcessor, TicketProcessorManager
from backend.schemas import ConfirmUploadRequest

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


@router.post("/{ds_id}/activate")
async def activate_datasource(
    ds_id: int,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """将指定数据源设为当前活跃数据源（其他数据源自动取消活跃）。"""
    # 1. 将所有数据源设为 inactive
    await db.execute(
        __import__('sqlalchemy').update(DataSource).values(status='inactive')
    )

    # 2. 将目标数据源设为 active
    result = await db.execute(select(DataSource).where(DataSource.id == ds_id))
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    ds.status = 'active'

    # 3. 更新处理器管理器
    try:
        from backend.routers.chat import get_pm
        pm = get_pm()
        if pm:
            pm.set_primary(ds_id)
    except Exception:
        pass

    await db.commit()
    return {"message": f"已切换到数据源: {ds.name}", "datasource_id": ds_id}


@router.delete("/{ds_id}")
async def delete_datasource(
    ds_id: int,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """删除数据源（同时清理关联报表、处理器、文件）。"""
    from backend.models import Report

    result = await db.execute(select(DataSource).where(DataSource.id == ds_id))
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    # 1. 删除关联报表
    report_result = await db.execute(select(Report).where(Report.datasource_id == ds_id))
    for report in report_result.scalars().all():
        await db.delete(report)

    # 2. 从处理器管理器中移除
    try:
        from backend.routers.chat import get_pm
        pm = get_pm()
        if pm:
            pm.remove(ds_id)
    except Exception:
        pass

    # 3. 删除上传的文件
    if ds.file_path:
        try:
            from pathlib import Path
            p = Path(ds.file_path)
            if p.exists():
                p.unlink()
        except Exception:
            pass

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
        processor = TicketProcessor(str(upload_path))
        _ = processor.df  # 触发加载
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

    if 'status' in processor.df.columns:
        sd = processor.get_status_distribution()
        charts.append(_build_chart(
            chart_renderer.render_pie, 'pie',
            'status', '工单状态分布',
            sd['labels'], sd['values'],
        ))

    if 'service_group' in processor.df.columns:
        sg = processor.get_service_group_distribution()
        charts.append(_build_chart(
            chart_renderer.render_horizontal_bar, 'horizontal_bar',
            'service_group', '服务组工单量排名',
            sg['labels'], sg['values'],
        ))

    if 'business_system' in processor.df.columns:
        bs = processor.get_business_system_distribution()
        charts.append(_build_chart(
            chart_renderer.render_horizontal_bar, 'horizontal_bar',
            'business_system', '业务系统分布',
            bs['labels'], bs['values'],
        ))

    if 'fault_group' in processor.df.columns:
        fg = processor.get_fault_group_distribution()
        charts.append(_build_chart(
            chart_renderer.render_pie, 'pie',
            'fault_group', '故障原因分组',
            fg['labels'], fg['values'],
        ))

    if 'created_week' in processor.df.columns:
        wt = processor.get_weekly_trend()
        charts.append(_build_chart(
            chart_renderer.render_line, 'line',
            'weekly_trend', '每周工单趋势',
            wt['labels'], [{'name': '工单数', 'data': wt['values']}],
        ))

    if 'assignee' in processor.df.columns:
        ad = processor.get_assignee_distribution()
        charts.append(_build_chart(
            chart_renderer.render_horizontal_bar, 'horizontal_bar',
            'assignee', '责任人处理量 TOP15',
            ad['labels'], ad['values'],
        ))

    # 生成洞察 + KPI + 数据表
    insights = processor.get_summary_kpis()
    kpis = insights
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


def _build_data_table(processor: TicketProcessor, total: int) -> dict:
    """构建数据明细表（前 100 行原始数据 + 汇总行）。"""
    df = processor.df.head(100)
    headers = ['序号', '标题', '状态', '请求人', '责任人', '服务组', '创建时间']
    rows = []
    for i, (_, row) in enumerate(df.iterrows(), start=1):
        rows.append([
            i,
            str(row.get('title', '')),
            str(row.get('status', '')),
            str(row.get('requester', '')),
            str(row.get('responsible_person', '')),
            str(row.get('service_group', '')),
            str(row.get('created_at', '')),
        ])
    rows.append(['', '', '', '', '', '', f'合计: {total} 件 (展示前100行)'])
    return {'headers': headers, 'rows': rows}


# ============================================================
# 两阶段上传：预览 → 确认
# ============================================================

TEMP_DIR = Path(__file__).parent.parent / "data" / "temp_uploads"


def _auto_map_columns(excel_columns: list[str]) -> tuple[dict, list[str], list[str], list[str]]:
    """自动映射 Excel 列名到系统字段。

    Returns:
        (suggested_mapping, unmapped_columns, unmapped_fields, warnings)
        suggested_mapping: {excel_col: {"field": str, "confidence": float}}
        unmapped_columns: Excel 中未映射的列
        unmapped_fields: 系统中未被映射的字段
        warnings: 告警信息
    """
    col_map = TicketProcessor.COL_MAP
    # 反向映射：english_field -> chinese_name
    reverse_map = {v: k for k, v in col_map.items()}

    suggested = {}
    matched_fields = set()
    warnings = []

    for excel_col in excel_columns:
        # 1. 精确匹配
        if excel_col in col_map:
            suggested[excel_col] = {"field": col_map[excel_col], "confidence": 1.0}
            matched_fields.add(col_map[excel_col])
            continue

        # 2. 包含匹配（如 "请求人部门" 包含 "部门"）
        matched = False
        for chinese_name, english_field in col_map.items():
            if chinese_name in excel_col or excel_col in chinese_name:
                if english_field not in matched_fields:
                    suggested[excel_col] = {"field": english_field, "confidence": 0.7}
                    matched_fields.add(english_field)
                    matched = True
                    if len(chinese_name) < len(excel_col):
                        warnings.append(f"列「{excel_col}」模糊匹配到「{chinese_name}」→ {english_field}，请确认")
                    break

        # 3. 未匹配
        if not matched:
            suggested[excel_col] = {"field": "", "confidence": 0.0}

    unmapped_columns = [col for col, m in suggested.items() if not m["field"]]
    unmapped_fields = [f for f in reverse_map.keys() if f not in matched_fields]

    return suggested, unmapped_columns, unmapped_fields, warnings


@router.post("/upload/preview")
async def upload_preview(
    file: UploadFile = File(...),
    user: User = Depends(require_admin),
):
    """阶段1：上传文件 → 自动映射 → 返回预览（不导入数据）。"""
    filename = file.filename or "upload.xlsx"
    if not filename.lower().endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx / .xls 格式文件")

    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # 保存临时文件
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r'[^\w\-.]', '_', filename)
    temp_path = TEMP_DIR / f"{ts}_{safe_name}"
    with temp_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        # 读取完整文件获取总行数和列统计
        df_full = pd.read_excel(str(temp_path), sheet_name=0)
        total_rows = len(df_full)

        # 读取前 5 行作为样本
        df_sample = df_full.head(5)

        # 自动映射
        excel_columns = list(df_full.columns)
        suggested_mapping, unmapped_columns, unmapped_fields, warnings = _auto_map_columns(excel_columns)

        # 列统计
        column_stats = {}
        for col in excel_columns:
            col_data = df_full[col]
            column_stats[col] = {
                "dtype": str(col_data.dtype),
                "null_count": int(col_data.isna().sum()),
                "null_rate": round(float(col_data.isna().mean()), 4),
                "unique_count": int(col_data.nunique()),
            }

        # 样本数据
        sample_data = []
        for _, row in df_sample.iterrows():
            sample_data.append({col: str(row[col]) if pd.notna(row[col]) else None for col in excel_columns})

        # 可用的系统字段列表
        available_fields = [
            {"key": v, "label": f"{k} ({v})"}
            for k, v in TicketProcessor.COL_MAP.items()
        ]

        return {
            "temp_path": str(temp_path),
            "filename": filename,
            "total_rows": total_rows,
            "suggested_mapping": suggested_mapping,
            "unmapped_columns": unmapped_columns,
            "unmapped_fields": unmapped_fields,
            "available_fields": available_fields,
            "sample_data": sample_data,
            "warnings": warnings,
            "column_stats": column_stats,
        }
    except Exception as e:
        # 清理临时文件
        if temp_path.exists():
            temp_path.unlink()
        raise HTTPException(status_code=400, detail=f"Excel 预览失败: {e}")


@router.post("/upload/confirm")
async def upload_confirm(
    req: ConfirmUploadRequest,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """阶段2：用户确认映射 → 正式导入 → 提取元数据 → 生成报表。"""
    temp_path = Path(req.temp_path)
    if not temp_path.exists():
        raise HTTPException(status_code=400, detail="临时文件不存在或已过期，请重新上传")

    try:
        # 构建自定义列映射（只包含用户确认的映射）
        custom_col_map = {}
        for excel_col, system_field in req.field_mapping.items():
            if system_field:  # 跳过空映射（用户选择"跳过"的列）
                custom_col_map[excel_col] = system_field

        # 创建 TicketProcessor（使用自定义映射）
        processor = TicketProcessor(str(temp_path), custom_col_map=custom_col_map if custom_col_map else None)
        _ = processor.df  # 触发加载

        total = len(processor.df)
        ds_name = req.datasource_name or Path(req.filename).stem

        # 移动到永久存储
        UPLOAD_DIR = Path(__file__).parent.parent / "data" / "uploads"
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r'[^\w\-.]', '_', req.filename)
        perm_path = UPLOAD_DIR / f"{ts}_{safe_name}"
        shutil.move(str(temp_path), str(perm_path))

        # 将其他数据源设为 inactive（单选模式）
        from sqlalchemy import update as sa_update
        await db.execute(
            sa_update(DataSource)
            .values(status='inactive')
        )

        # 创建 DataSource 记录
        ds = DataSource(
            name=ds_name,
            type='excel',
            config=json.dumps({'uploaded_path': str(perm_path)}, ensure_ascii=False),
            field_mapping=json.dumps(custom_col_map, ensure_ascii=False) if custom_col_map else None,
            status='active',
            record_count=total,
            file_path=str(perm_path),
            last_updated=datetime.now(timezone.utc),
        )
        db.add(ds)
        await db.flush()
        ds_id = ds.id

        # 注册到 processor_manager
        from backend.routers.chat import get_pm
        pm = get_pm()
        if pm:
            pm.register(datasource_id=ds_id, file_path=str(perm_path), field_mapping=custom_col_map if custom_col_map else None)
            pm.set_primary(ds_id)

        # 提取元数据（如果 MemoryService 可用）
        from backend.routers.chat import get_memory_service
        memory_svc = get_memory_service()
        if memory_svc:
            try:
                await memory_svc.extract_and_save(ds_id, processor.df, custom_col_map)
            except Exception as e:
                print(f"Warning: 元数据提取失败: {e}")

        # 生成报表（复用现有逻辑）
        from backend.services import chart_renderer

        charts = []
        if 'status' in processor.df.columns:
            sd = processor.get_status_distribution()
            charts.append(_build_chart(chart_renderer.render_pie, 'pie', 'status', '工单状态分布', sd['labels'], sd['values']))
        if 'service_group' in processor.df.columns:
            sg = processor.get_service_group_distribution()
            charts.append(_build_chart(chart_renderer.render_horizontal_bar, 'horizontal_bar', 'service_group', '服务组工单量排名', sg['labels'], sg['values']))
        if 'business_system' in processor.df.columns:
            bs = processor.get_business_system_distribution()
            charts.append(_build_chart(chart_renderer.render_horizontal_bar, 'horizontal_bar', 'business_system', '业务系统分布', bs['labels'], bs['values']))
        if 'fault_group' in processor.df.columns:
            fg = processor.get_fault_group_distribution()
            charts.append(_build_chart(chart_renderer.render_pie, 'pie', 'fault_group', '故障原因分组', fg['labels'], fg['values']))
        if 'created_week' in processor.df.columns:
            wt = processor.get_weekly_trend()
            charts.append(_build_chart(chart_renderer.render_line, 'line', 'weekly_trend', '每周工单趋势', wt['labels'], [{'name': '工单数', 'data': wt['values']}]))
        if 'responsible_person' in processor.df.columns or 'assignee' in processor.df.columns:
            ad = processor.get_assignee_distribution()
            charts.append(_build_chart(chart_renderer.render_horizontal_bar, 'horizontal_bar', 'assignee', '责任人处理量 TOP15', ad['labels'], ad['values']))

        insights = processor.generate_insights()
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
            datasource_id=ds_id,
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
            'datasource_id': ds_id,
            'total_records': total,
            'filename': req.filename,
            'chart_count': len(charts),
            'insight_count': len(insights),
            'datasource_name': ds_name,
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        # 清理临时文件
        if temp_path.exists():
            temp_path.unlink()
        raise HTTPException(status_code=400, detail=f"数据导入失败: {e}")


@router.get("/{ds_id}/metadata")
async def get_datasource_metadata(
    ds_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取数据源元数据。"""
    from backend.routers.chat import get_memory_service
    memory_svc = get_memory_service()
    if not memory_svc:
        raise HTTPException(status_code=503, detail="记忆服务不可用")

    metadata = await memory_svc.get_metadata(ds_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="元数据不存在")
    return metadata


@router.get("/with-metadata")
async def list_datasources_with_metadata(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取所有数据源及其元数据摘要。"""
    result = await db.execute(select(DataSource).order_by(DataSource.created_at.desc()))
    items = result.scalars().all()

    from backend.routers.chat import get_memory_service
    memory_svc = get_memory_service()

    datasources = []
    for d in items:
        ds_info = {
            'id': d.id, 'name': d.name, 'type': d.type,
            'status': d.status, 'record_count': d.record_count,
            'last_updated': d.last_updated, 'created_at': d.created_at,
            'file_path': d.file_path,
            'metadata': None,
        }
        if memory_svc:
            try:
                ds_info['metadata'] = await memory_svc.get_metadata(d.id)
            except Exception:
                pass
        datasources.append(ds_info)

    return datasources
