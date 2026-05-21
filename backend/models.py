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


class DataSource(Base):
    __tablename__ = "datasources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    type = Column(String(20), nullable=False)
    config = Column(Text)
    field_mapping = Column(Text)
    status = Column(String(20), default="active")
    record_count = Column(Integer, default=0)
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
