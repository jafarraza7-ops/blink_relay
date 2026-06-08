"""
models/request.py — SQLAlchemy ORM models and domain enums for Blink Relay.

Defines every database table used by the intake workflow:
  - Request      — the core intake record submitted by a stakeholder
  - Message      — threaded comments, clarification Q&A, and status-change notes
  - Attachment   — file uploads stored in Azure Blob, referenced by blob_name
  - AuditLog     — immutable log of every status change and field edit
  - User         — local mirror of Entra ID users (upserted on login)

Also defines the ALLOWED_TRANSITIONS state machine which enforces the legal
status progression: Submitted → InReview → ... → Approved/Rejected → Closed.
"""
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

from pydantic import field_validator, BaseModel
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


# ── Enums ─────────────────────────────────────────────────────────────────────

class MessageType(StrEnum):
    """Distinguishes message intent so the UI can render each type differently
    (e.g. status banners vs. conversation bubbles vs. Q&A threads)."""
    COMMENT = "comment"
    CLARIFICATION_QUESTION = "clarification_question"
    CLARIFICATION_RESPONSE = "clarification_response"
    STATUS_CHANGE = "status_change"


class Pod(StrEnum):
    """Engineering product areas. Each pod owns specific Blink products/services.

    Pod represents the team or product area responsible for handling a request.
    Database values remain unchanged for compatibility, but users see business-friendly
    labels in the UI that focus on product impact rather than technical team names.

    Mapping (enum value → user-friendly display label):
      - Charger → "Charging Stations"
      - Driver → "Driver Mobile App"
      - Revenue → "Payments & Billing"
      - Data → "Data & Analytics"
      - DevOps → "System & Infrastructure"
      - Denali → "Enterprise Fleet"
      - Unknown → "Not yet classified"
    """
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
    CANCELLED = "Cancelled"


# ── Priority mapping ──────────────────────────────────────────────────────────
# Maps internal Priority enum to Jira priority labels (P0–P3 levels).
# Single source of truth — used by jira_service.py when creating/updating tickets.

JIRA_PRIORITY_MAP: dict[Priority, str] = {
    Priority.CRITICAL: "P0 - CRITICAL",
    Priority.HIGH: "P1 - HIGH",
    Priority.MEDIUM: "P2 - MEDIUM",
    Priority.LOW: "P3 - LOW",
}


# ── State machine ─────────────────────────────────────────────────────────────

# Defines every legal status transition. Endpoints call _validate_transition()
# against this map before applying any status change, keeping the state machine
# authoritative in one place rather than duplicated across routes.
ALLOWED_TRANSITIONS: dict[RequestStatus, set[RequestStatus]] = {
    RequestStatus.SUBMITTED:     {RequestStatus.IN_REVIEW, RequestStatus.AWAITING_INFO, RequestStatus.APPROVED, RequestStatus.REJECTED, RequestStatus.CANCELLED},
    RequestStatus.IN_REVIEW:     {RequestStatus.AWAITING_INFO, RequestStatus.APPROVED, RequestStatus.REJECTED, RequestStatus.IN_PROGRESS, RequestStatus.CANCELLED},
    RequestStatus.AWAITING_INFO: {RequestStatus.INFO_RECEIVED, RequestStatus.CANCELLED},
    RequestStatus.INFO_RECEIVED: {RequestStatus.IN_REVIEW, RequestStatus.APPROVED, RequestStatus.CANCELLED},
    RequestStatus.REJECTED:      set(),
    RequestStatus.IN_PROGRESS:   {RequestStatus.COMPLETED},
    RequestStatus.COMPLETED:     {RequestStatus.CLOSED},
    RequestStatus.CLOSED:        set(),
    RequestStatus.CANCELLED:     set(),
}


# ── ORM models ────────────────────────────────────────────────────────────────

class User(Base):
    """Local mirror of an Entra ID user. Upserted on every successful login
    so the app has display names and roles without calling Graph on each request."""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # oid is the Entra object ID — the stable, tenant-scoped identifier used to
    # correlate all activity back to a single user across email changes.
    oid: Mapped[Optional[str]] = mapped_column(String(36), unique=True, nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    roles: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auth_source: Mapped[Optional[str]] = mapped_column(String(20), default="azure_ad", nullable=True)
    last_login_method: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )




class EmailLoginToken(Base):
    """Secure, one-time-use tokens for email-based authentication.
    
    Tokens are hashed before storage to prevent disclosure if the database
    is compromised. Only the hash is stored; the plaintext token is sent
    to the user and never persisted.
    """
    __tablename__ = "email_login_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    is_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    used_ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    used_user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    request_ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    invalidation_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    invalidated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])

class TimelineEventResponse(BaseModel):
    """Single event in request lifecycle timeline.

    Represents a point-in-time change to the request: submission, status change,
    approval, rejection, or clarification. Used to render the visual timeline
    in the request detail view.
    """
    timestamp: datetime
    action: str  # "submitted", "status_change", "approved", "rejected", "info_provided", etc.
    actor_name: str  # Who made the change
    actor_email: Optional[str]
    details: str  # Human-readable description
    status: Optional[str]  # New status after action

    model_config = {"from_attributes": True}


class Request(Base):
    """Core intake record. One row per stakeholder submission."""
    __tablename__ = "requests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Human-readable reference like BLR-2024-0042. Generated by _ensure_reference_id()
    # after insert because SQLite lacks the DB-side trigger used in Postgres.
    reference_id: Mapped[Optional[str]] = mapped_column(String(20), unique=True, nullable=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    request_type: Mapped[RequestType] = mapped_column(
        Enum(RequestType, name="request_type", native_enum=False), nullable=False
    )
    pod: Mapped[Pod] = mapped_column(Enum(Pod, name="pod", native_enum=False), nullable=False)
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, name="priority", native_enum=False), nullable=False, default=Priority.MEDIUM
    )
    # Stored as a JSON array (e.g. ["NA", "UK"]). Migration 007 changed this
    # from a single VARCHAR column, so always treat it as a list in code.
    region: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=lambda: ["NA"]
    )
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, name="request_status", native_enum=False),
        nullable=False,
        default=RequestStatus.SUBMITTED,
    )

    business_problem: Mapped[str] = mapped_column(Text, nullable=False)
    # expected_outcome is optional for Defects (steps_to_reproduce takes priority).
    expected_outcome: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # steps_to_reproduce is optional for Feature requests.
    steps_to_reproduce: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    affected_area: Mapped[str] = mapped_column(String(500), nullable=False)
    additional_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitter_oid: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    submitter_email: Mapped[str] = mapped_column(String(254), nullable=False)
    submitter_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Rejection fields are only populated when status == REJECTED.
    # rejection_reason is a short category (e.g. "Out of scope");
    # rejection_comment is an optional free-text elaboration shown to the requestor.
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    rejection_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rejected_by_oid: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Populated by task_create_jira_ticket after a PM approves the request.
    jira_ticket_key: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    jira_ticket_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # JSM (Jira Service Management) — customer-facing ticket created on submission
    jsm_ticket_key: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    jsm_ticket_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    jsm_resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Tracks when the last 72-hour pending reminder was sent to PMs.
    # Used to prevent duplicate reminders within a 24-hour window for the same request.
    # If a request remains in SUBMITTED or IN_REVIEW for 72+ hours without status update,
    # a reminder is sent to all PMs. This field is updated to the current timestamp
    # after the reminder is sent, allowing another reminder after 24+ hours have passed.
    reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

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
    """A single message in a request's thread. Can be a reviewer comment,
    a PM clarification question, a submitter response, or a system status-change note."""
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_oid: Mapped[str] = mapped_column(String(36), nullable=False)
    author_email: Mapped[str] = mapped_column(String(254), nullable=False)
    author_name: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Internal messages are visible only to reviewers/PMs in the admin UI,
    # not to the requestor or via JSM.
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    message_type: Mapped[MessageType] = mapped_column(
        Enum(MessageType, name="message_type_enum", native_enum=False),
        nullable=False,
        default=MessageType.COMMENT,
    )
    # JSM comment ID once synced — null until the comment is mirrored to JSM
    jsm_comment_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # Array of mentioned user OIDs (e.g. ["oid-123", "oid-456"])
    mentions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    request: Mapped[Request] = relationship("Request", back_populates="messages")


class Attachment(Base):
    """Metadata record for a file uploaded to Azure Blob Storage.
    The actual bytes live in blob_name; this row tracks ownership and lets the
    app generate SAS download URLs without hitting Blob Storage on every read."""
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
    """Append-only record of every meaningful action taken on a request.
    Used for compliance, debugging, and displaying history in the UI timeline."""
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
