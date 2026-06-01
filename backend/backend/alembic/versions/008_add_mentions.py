"""Add mentions support to messages table.

Revision ID: 008
Revises: 007
Create Date: 2026-06-01

"""
from alembic import op
import sqlalchemy as sa


revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add mentions column to messages table (JSON array of mentioned user OIDs)
    op.add_column('messages', sa.Column('mentions', sa.JSON(), nullable=True, server_default='[]'))


def downgrade() -> None:
    op.drop_column('messages', 'mentions')
