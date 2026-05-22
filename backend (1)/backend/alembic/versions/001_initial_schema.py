"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-01 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("oid", sa.String(36), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("roles", sa.JSON(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_oid"), "users", ["oid"], unique=True)

    op.create_table(
        "requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reference_id", sa.String(20), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column(
            "request_type",
            sa.Enum("Feature", "Defect", name="request_type"),
            nullable=False,
        ),
        sa.Column(
            "pod",
            sa.Enum("Charger", "Driver", "Revenue", "Data", "DevOps", "Denali", "Unknown", name="pod"),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.Enum("Critical", "High", "Medium", "Low", name="severity"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "Submitted", "InReview", "AwaitingInfo", "InfoReceived",
                "Approved", "Rejected", "InProgress", "Completed", "Closed",
                name="request_status",
            ),
            nullable=False,
        ),
        sa.Column("business_problem", sa.Text(), nullable=False),
        sa.Column("expected_outcome", sa.Text(), nullable=True),
        sa.Column("steps_to_reproduce", sa.Text(), nullable=True),
        sa.Column("affected_area", sa.String(500), nullable=False),
        sa.Column("additional_context", sa.Text(), nullable=True),
        sa.Column("target_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitter_oid", sa.String(36), nullable=False),
        sa.Column("submitter_email", sa.String(254), nullable=False),
        sa.Column("submitter_name", sa.String(200), nullable=False),
        sa.Column("rejection_reason", sa.String(100), nullable=True),
        sa.Column("rejection_comment", sa.Text(), nullable=True),
        sa.Column("rejected_by_oid", sa.String(36), nullable=True),
        sa.Column("jira_ticket_key", sa.String(30), nullable=True),
        sa.Column("jira_ticket_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference_id"),
    )
    op.create_index(op.f("ix_requests_submitter_oid"), "requests", ["submitter_oid"], unique=False)

    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("author_oid", sa.String(36), nullable=False),
        sa.Column("author_email", sa.String(254), nullable=False),
        sa.Column("author_name", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_internal", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_messages_request_id"), "messages", ["request_id"], unique=False)

    op.create_table(
        "attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("blob_name", sa.String(500), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_oid", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_attachments_request_id"), "attachments", ["request_id"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("actor_oid", sa.String(36), nullable=False),
        sa.Column("actor_email", sa.String(254), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("previous_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("event_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_request_id"), "audit_logs", ["request_id"], unique=False)

    # Auto-generate BLR-YYYY-NNNN reference IDs.
    # PostgreSQL uses a trigger function; SQLite generates IDs in application code.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("""
            CREATE OR REPLACE FUNCTION generate_reference_id()
            RETURNS trigger LANGUAGE plpgsql AS $$
            DECLARE
                year_part TEXT := to_char(NOW(), 'YYYY');
                seq_num   INT;
            BEGIN
                SELECT COALESCE(MAX(CAST(SUBSTRING(reference_id FROM 10) AS INT)), 0) + 1
                  INTO seq_num
                  FROM requests
                 WHERE reference_id LIKE 'BLR-' || year_part || '-%';
                NEW.reference_id := 'BLR-' || year_part || '-' || LPAD(seq_num::TEXT, 4, '0');
                RETURN NEW;
            END;
            $$;
        """)
        op.execute("""
            CREATE TRIGGER trg_requests_reference_id
            BEFORE INSERT ON requests
            FOR EACH ROW
            WHEN (NEW.reference_id IS NULL)
            EXECUTE FUNCTION generate_reference_id();
        """)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_requests_reference_id ON requests")
        op.execute("DROP FUNCTION IF EXISTS generate_reference_id")
    op.drop_table("audit_logs")
    op.drop_table("attachments")
    op.drop_table("messages")
    op.drop_table("requests")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS request_status")
    op.execute("DROP TYPE IF EXISTS severity")
    op.execute("DROP TYPE IF EXISTS pod")
    op.execute("DROP TYPE IF EXISTS request_type")
