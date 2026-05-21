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
    charts: list[ChartData] = []
    insights: list[str] = []
    data_table: Optional[dict] = None
    report_id: Optional[int] = None


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


# --- Skills ---
class SkillOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    enabled: bool
    supported_chart_types: Optional[str]
    created_at: Optional[datetime]
