from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey, func
from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255))
    display_name = Column(String(100))
    role = Column(String(20), default="user")
    auth_provider = Column(String(20), default="local")
    created_at = Column(DateTime, server_default=func.now())
    last_login = Column(DateTime)


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200))
    context_state = Column(Text)
    context_summary = Column(Text)  # 对话摘要，用于跨轮引用
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    role = Column(String(10), nullable=False)
    content = Column(Text)
    has_report = Column(Boolean, default=False)
    report_id = Column(Integer, ForeignKey("reports.id"))
    created_at = Column(DateTime, server_default=func.now())


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    title = Column(String(300))
    datasource_id = Column(Integer, ForeignKey("datasources.id"))
    skill_id = Column(Integer, ForeignKey("skills.id"))
    report_type = Column(String(50))
    chart_config = Column(Text)
    data_payload = Column(Text)
    insights = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


class PendingDimension(Base):
    """待确认的分析维度 — 用户查询了预设映射表之外的维度时自动记录。"""
    __tablename__ = "pending_dimensions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    query_text = Column(String(200), nullable=False)       # 用户原始查询（如"按紧急程度分析"）
    matched_column = Column(String(100), nullable=False)    # 模糊匹配到的列名（英文）
    matched_label = Column(String(100))                     # 列的中文名（从 COL_MAP 反查）
    sample_values = Column(Text)                            # JSON: 该列的前5个去重值
    usage_count = Column(Integer, default=1)                # 被查询的次数
    status = Column(String(20), default="pending")          # pending / approved / rejected
    approved_group_by = Column(String(50))                  # 用户批准后的 group_by key
    reviewed_by = Column(Integer, ForeignKey("users.id"))   # 审核人
    reviewed_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class DataSource(Base):
    __tablename__ = "datasources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    type = Column(String(20), nullable=False)
    config = Column(Text)
    field_mapping = Column(Text)
    status = Column(String(20), default="active")
    record_count = Column(Integer, default=0)
    file_path = Column(Text)  # 持久化文件路径
    last_updated = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    datasource_id = Column(Integer, ForeignKey("datasources.id"))
    enabled = Column(Boolean, default=True)
    supported_chart_types = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(50))
    resource_type = Column(String(50))
    resource_id = Column(Integer)
    detail = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


# ============================================================
# 长记忆机制相关表
# ============================================================

class UserPreference(Base):
    """用户偏好记忆 — 记录用户常用的分析维度、筛选条件等。"""
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    preference_key = Column(String(100), nullable=False)   # e.g. "preferred_dimensions", "default_filters"
    preference_value = Column(Text, nullable=False)         # JSON
    usage_count = Column(Integer, default=1)
    updated_at = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())


class AnalysisHistory(Base):
    """分析历史记忆 — 保存每次分析的结论和关键发现。"""
    __tablename__ = "analysis_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    datasource_id = Column(Integer, ForeignKey("datasources.id"))
    analysis_type = Column(String(50))          # e.g. "status", "root_cause", "ops_quality"
    summary = Column(Text)                       # 分析摘要
    key_findings = Column(Text)                  # JSON: insights 数组
    data_snapshot = Column(Text)                 # JSON: KPI/图表概要
    tags = Column(String(500))                   # 逗号分隔的检索标签
    created_at = Column(DateTime, server_default=func.now())


class DatasourceMetadata(Base):
    """数据源元数据记忆 — 自动提取的字段结构和数据特征。"""
    __tablename__ = "datasource_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    datasource_id = Column(Integer, ForeignKey("datasources.id"), nullable=False, unique=True)
    field_structure = Column(Text)      # JSON: [{name, type, unique_count, top_values, null_count}]
    data_characteristics = Column(Text)  # JSON: {total_rows, time_range:{min,max}, column_count}
    quality_metrics = Column(Text)       # JSON: {null_rates, duplicate_count, anomaly_flags}
    key_distributions = Column(Text)     # JSON: {status_dist, service_group_dist, ...}
    extracted_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())
