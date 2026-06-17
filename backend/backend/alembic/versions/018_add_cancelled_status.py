"""Add Cancelled value to request_status enum.

Revision ID: 018
Revises: 017
Create Date: 2026-06-17 00:00:00.000000
"""
from alembic import op

revision = '018'
down_revision = '017'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE request_status ADD VALUE IF NOT EXISTS 'Cancelled'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; downgrade is a no-op.
    pass
