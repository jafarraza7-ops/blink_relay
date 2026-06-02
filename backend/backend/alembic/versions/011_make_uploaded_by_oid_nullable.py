"""Make uploaded_by_oid nullable in attachments table for email users.

Revision ID: 011
Revises: 010
Create Date: 2026-06-02
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite doesn't support ALTER COLUMN, so use batch operations
    with op.batch_alter_table("attachments", schema=None) as batch_op:
        batch_op.alter_column("uploaded_by_oid", existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    # Revert to NOT NULL
    with op.batch_alter_table("attachments", schema=None) as batch_op:
        batch_op.alter_column("uploaded_by_oid", existing_type=sa.String(length=255), nullable=False)
