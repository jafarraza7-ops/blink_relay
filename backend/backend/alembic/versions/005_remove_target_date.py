"""remove target_date

Revision ID: 005
Revises: 004
Create Date: 2026-05-21

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('requests') as batch_op:
        batch_op.drop_column('target_date')


def downgrade() -> None:
    with op.batch_alter_table('requests') as batch_op:
        batch_op.add_column(sa.Column('target_date', sa.DateTime(timezone=True), nullable=True))
