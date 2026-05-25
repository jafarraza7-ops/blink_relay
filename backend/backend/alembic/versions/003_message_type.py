"""add message_type column to messages

Revision ID: 003
Revises: 002
Create Date: 2026-05-15 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("messages") as batch_op:
        batch_op.add_column(
            sa.Column(
                "message_type",
                sa.String(50),
                nullable=False,
                server_default="comment",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("messages") as batch_op:
        batch_op.drop_column("message_type")
