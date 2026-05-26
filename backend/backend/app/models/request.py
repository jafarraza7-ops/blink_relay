from __future__ import annotations

import uuid
from datetime import datetime, timezone
try:
    from enum import StrEnum
except ImportError:  # Python < 3.11
    from enum import Enum
    class StrEnum(str, Enum):
        pass
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MessageType(StrEnum):
    COMMENT = "comment"
    CLARIFICATION_QUESTION = "clarification_question"
    CLARIFICATION_RESPONSE = "clarification_response"
    STATUS_CHANGE = "status_change"


class Pod(StrEnum):
    CHARGER = "Charger"
    DRIVER = "Driver"
    REVENUE = "Revenue"
    DATA = "Data"
    DEVOPS = "DevOps"
    DENALI = "Denali"
    UNKNOWN = "Unknown"


class Region(StrEnum):
    NA = "NA"
    UK = "UK"
    EU = "EU"


class RequestType(StrEnum):
    FEATURE = "Feature"
    DEFECT = "Defect"


class Priority(StrEnum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class RequestStatus(StrEnum):
    SUBMITTED = "Submitted"
    IN_REVIEW = "InReview"
    AWAITING_INFO = "AwaitingInfo"
    INFO_RECEIVED = "InfoReceived"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    IN_PROGRESS = "InProgress"
    COMPLETED = "Completed"
    CLOSED = "Closed"


ALLOWED_TRANSITIONS: dict[RequestStatus, set[RequestStatus]] = {
    RequestStatus.SUBMITTED:     {RequestStatus.IN_REVIEW, RequestStatus.AWAITING_INFO, RequestStatus.APPROVED, RequestStatus.REJECTED},
    RequestStatus.IN_REVIEW:     {RequestStatus.AWAITING_INFO, RequestStatus.APPROVED, RequestStatus.REJECTED, RequestStatus.IN_PROGRESS},
    RequestStatus.AWAITING_INFO: {RequestStatus.INFO_RECEIVED},
    RequestStatus.INFO_RECEIVED: {RequestStatus.IN_REVIEW, RequestStatus.APPROVED},
    RequestStatus.APPROVED:      {RequestStatus.IN_REVIEW, RequestStatus.IN_PROGRESS, RequestStatus.REJECTED},
    RequestStatus.REJECTED:      set(),
    RequestStatus.IN_PROGRESS:   {RequestStatus.COMPLETED},
    RequestStatus.COMPLETED:     {RequestStatus.CLOSED},
    RequestStatus.CLOSED:        set(),
}


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    oid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    roles: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class Request(Base):
    __tablename__ = "requests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    reference_id: Mapped[Optional[str]] = mapped_column(String(20), unique=True, nullable=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    request_type: Mapped[RequestType] = mapped_column(
        Enum(RequestType, name="request_type"), nullable=False
    )
    pod: Mapped[Pod] = mapped_column(Enum(Pod, name="pod"), nullable=False)
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, name="priority"), nullable=False, default=Priority.MEDIUM
    )
    region: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=lambda: ["NA"]
    )
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, name="request_status"),
        nullable=False,
        default=RequestStatus.SUBMITTED,
    )

    business_problem: Mapped[str] = mapped_column(Text, nullable=False)
    expected_outcome: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    steps_to_reproduce: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    affected_area: Mapped[str] = mapped_column(String(500), nullable=False)
    additional_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitter_oid: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    submitter_email: Mapped[str] = mapped_column(String(254), nullable=False)
    submitter_name: Mapped[str] = mapped_column(String(200), nullable=False)

    rejection_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    rejection_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rejected_by_oid: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    jira_ticket_key: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    jira_ticket_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # JSM (Jira Service Management) — customer-facing ticket created on submission
    jsm_ticket_key: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    jsm_ticket_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    jsm_resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    messages: Mapped[list[Message]] = relationship(
        "Message", back_populates="request", cascade="all, delete-orphan", lazy="select"
    )
    attachments: Mapped[list[Attachment]] = relationship(
        "Attachment", back_populates="request", cascade="all, delete-orphan", lazy="select"
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(
        "AuditLog", back_populates="request", cascade="all, delete-orphan", lazy="select"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_oid: Mapped[str] = mapped_column(String(36), nullable=False)
    author_email: Mapped[str] = mapped_column(String(254), nullable=False)
    author_name: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    message_type: Mapped[MessageType] = mapped_column(
        Enum(MessageType, name="message_type_enum", native_enum=False),
        nullable=False,
        default=MessageType.COMMENT,
    )
    # JSM comment ID once synced — null until the comment is mirrored to JSM
    jsm_comment_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    request: Mapped[Request] = relationship("Request", back_populates="messages")


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    blob_name: Mapped[str] = mapped_column(String(500), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by_oid: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    request: Mapped[Request] = relationship("Request", back_populates="attachments")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_oid: Mapped[str] = mapped_column(String(36), nullable=False)
    actor_email: Mapped[str] = mapped_column(String(254), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    previous_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    request: Mapped[Request] = relationship("Request", back_populates="audit_logs")
