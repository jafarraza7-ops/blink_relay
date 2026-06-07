"""Add reminder_sent_at field to track pending request reminder state

Revision ID: 015
Revises: 014
Create Date: 2026-06-07 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "requests",
        sa.Column(
            "reminder_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the last 72-hour pending reminder was sent to PMs; prevents duplicate reminders within 24h window",
        ),
    )


def downgrade() -> None:
    op.drop_column("requests", "reminder_sent_at")
