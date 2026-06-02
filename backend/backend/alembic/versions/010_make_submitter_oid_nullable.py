"""Make submitter_oid nullable for email-authenticated users.

Revision ID: 010
Revises: 009
Create Date: 2026-06-02
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite doesn't support ALTER COLUMN, so use batch operations
    with op.batch_alter_table("requests", schema=None) as batch_op:
        batch_op.alter_column("submitter_oid", existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    # Revert to NOT NULL
    with op.batch_alter_table("requests", schema=None) as batch_op:
        batch_op.alter_column("submitter_oid", existing_type=sa.String(length=255), nullable=False)
