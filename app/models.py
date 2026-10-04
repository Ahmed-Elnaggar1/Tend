from datetime import datetime
from uuid import UUID as PyUUID, uuid4
from enum import StrEnum

from sqlalchemy import JSON, DateTime, String, func, Uuid, Enum, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class EventStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class State(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    DELETED = "deleted"

class Priority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id: Mapped[PyUUID] = mapped_column(Uuid(as_uuid=True), default=uuid4, primary_key=True)
    delivery_id: Mapped[str] = mapped_column(String,unique=True,nullable=False) 
    event_type: Mapped[str] = mapped_column(String,nullable=False)
    payload: Mapped[dict] = mapped_column(JSON,nullable=False)
    status: Mapped[EventStatus] = mapped_column(Enum(EventStatus),nullable=False,default=EventStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

class Issue(Base):
    __tablename__ = "issues"
    id: Mapped[PyUUID] = mapped_column(Uuid(as_uuid=True), default=uuid4, primary_key=True)
    issue_number: Mapped[int] = mapped_column(Integer,nullable=False) 
    repo_name: Mapped[str] = mapped_column(String,nullable=False)
    github_id: Mapped[str] = mapped_column(String,unique=True,nullable=False)

    title: Mapped[str] = mapped_column(String,nullable=False)
    body: Mapped[str|None] = mapped_column(String,nullable=True)
    author: Mapped[str] = mapped_column(String,nullable=False)
    state: Mapped[State] = mapped_column(Enum(State),nullable=False,default=State.OPEN)

    priority: Mapped[Priority] = mapped_column(Enum(Priority),nullable=False,default=Priority.MEDIUM)
    ai_summary: Mapped[str|None] = mapped_column(String,nullable=True)
    draft_reply: Mapped[str|None] = mapped_column(String,nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
