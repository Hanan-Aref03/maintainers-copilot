from sqlalchemy import Column, String, DateTime, JSON, Text, Enum, ForeignKey, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func, text
from app.infra.database import Base
from app.infra.vector import Vector
import uuid
import enum

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MAINTAINER = "maintainer"

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(Enum(UserRole), default=UserRole.MAINTAINER)
    token_version = Column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Widget(Base):
    __tablename__ = "widgets"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    public_id = Column(String, unique=True, index=True)  # for the embed script
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    allowed_origins = Column(JSON, default=list)  # ["https://example.com"]
    theme = Column(
        JSON,
        default=lambda: {"primary_color": "#3b82f6", "position": "bottom-right"},
    )
    greeting = Column(Text, default="Hi! How can I help with issue triage?")
    enabled_tools = Column(JSON, default=lambda: ["classify", "rag", "memory"])
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class LongTermMemory(Base):
    __tablename__ = "long_term_memory"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    memory_type = Column(String)  # "semantic", "episodic", "procedural"
    content = Column(Text)
    embedding = Column(Vector(1536))  # for semantic search later
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    action = Column(String)  # "WRITE_MEMORY", "CLASSIFY_ISSUE", "CREATE_WIDGET"
    target = Column(String)  # e.g., "memory_id:xxx"
    details = Column(JSON)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
