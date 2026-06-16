from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


# --- Auth ---
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserOut(BaseModel):
    id: int
    username: str
    display_name: Optional[str]
    role: str

    class Config:
        from_attributes = True


# --- Chat ---
class ChatMessageRequest(BaseModel):
    message: str
    session_id: Optional[int] = None


class ChartData(BaseModel):
    id: str
    title: str
    type: str
    option: dict


class ChatResponse(BaseModel):
    message: str
    session_id: Optional[int] = None
    charts: list[ChartData] = []
    insights: list[str] = []
    data_table: Optional[dict] = None
    report_id: Optional[int] = None
    active_datasources: Optional[list[dict]] = None
    memory_hints: Optional[list[str]] = None
    deep_insights: Optional[list[dict]] = None  # 深度洞察卡片 [{tag, title, content, severity}]


class SessionOut(BaseModel):
    id: int
    title: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class MessageOut(BaseModel):
    id: int
    role: str
    content: Optional[str]
    has_report: bool
    report_id: Optional[int]
    created_at: Optional[datetime]


# --- Reports ---
class ReportOut(BaseModel):
    id: int
    title: Optional[str]
    datasource_id: Optional[int]
    skill_id: Optional[int]
    report_type: Optional[str]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class ReportDetail(ReportOut):
    chart_config: Optional[str]
    data_payload: Optional[str]
    insights: Optional[str]


# --- Data Sources ---
class DataSourceOut(BaseModel):
    id: int
    name: str
    type: str
    status: str
    record_count: int
    last_updated: Optional[datetime]
    created_at: Optional[datetime]


class ConfirmUploadRequest(BaseModel):
    """确认上传请求 — 用户确认字段映射后提交。"""
    temp_path: str
    filename: str
    field_mapping: dict[str, str]  # {excel_col: system_field}
    datasource_name: Optional[str] = None


# --- Skills ---
class SkillOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    enabled: bool
    supported_chart_types: Optional[str]
    created_at: Optional[datetime]
