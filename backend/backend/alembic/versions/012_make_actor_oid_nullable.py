"""Make actor_oid nullable in audit_logs for email-authenticated users.

Revision ID: 012
Revises: 011
Create Date: 2026-06-03
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("audit_logs", schema=None) as batch_op:
        batch_op.alter_column("actor_oid", existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("audit_logs", schema=None) as batch_op:
        batch_op.alter_column("actor_oid", existing_type=sa.String(length=255), nullable=False)
