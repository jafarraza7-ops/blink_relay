"""add region field to requests

Revision ID: 006
Revises: 005
Create Date: 2026-05-21

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('requests') as batch_op:
        batch_op.add_column(
            sa.Column('region', sa.String(10), nullable=False, server_default='NA')
        )


def downgrade() -> None:
    with op.batch_alter_table('requests') as batch_op:
        batch_op.drop_column('region')
