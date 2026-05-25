"""rename severity to priority

Revision ID: 004
Revises: 003
Create Date: 2026-05-20

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('requests') as batch_op:
        batch_op.alter_column(
            'severity',
            new_column_name='priority',
            existing_type=sa.Enum('Critical', 'High', 'Medium', 'Low', name='priority'),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('requests') as batch_op:
        batch_op.alter_column(
            'priority',
            new_column_name='severity',
            existing_type=sa.Enum('Critical', 'High', 'Medium', 'Low', name='severity'),
            nullable=False,
        )
