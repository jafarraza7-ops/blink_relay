"""add JSM ticket and comment tracking columns

Revision ID: 002
Revises: 001
Create Date: 2026-05-06 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("requests", sa.Column("jsm_ticket_key", sa.String(30), nullable=True))
    op.add_column("requests", sa.Column("jsm_ticket_url", sa.String(500), nullable=True))
    op.add_column("requests", sa.Column("jsm_resolved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("messages", sa.Column("jsm_comment_id", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "jsm_comment_id")
    op.drop_column("requests", "jsm_resolved_at")
    op.drop_column("requests", "jsm_ticket_url")
    op.drop_column("requests", "jsm_ticket_key")
