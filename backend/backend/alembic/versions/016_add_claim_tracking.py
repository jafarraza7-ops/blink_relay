"""Add PM claim tracking to prevent duplicate effort on requests

Revision ID: 016
Revises: 015
Create Date: 2026-06-08 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "requests",
        sa.Column(
            "claimed_by_oid",
            sa.String(36),
            nullable=True,
            index=True,
            comment="Azure AD OID of the PM currently working on this request",
        ),
    )
    op.add_column(
        "requests",
        sa.Column(
            "claimed_by_email",
            sa.String(254),
            nullable=True,
            comment="Email of the PM (fallback when user account is deleted)",
        ),
    )
    op.add_column(
        "requests",
        sa.Column(
            "claimed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when the claim was made",
        ),
    )


def downgrade() -> None:
    op.drop_column("requests", "claimed_at")
    op.drop_column("requests", "claimed_by_email")
    op.drop_column("requests", "claimed_by_oid")
