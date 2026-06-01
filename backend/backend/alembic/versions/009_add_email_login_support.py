"""Add email login tokens support.

Revision ID: 009
Revises: 008
Create Date: 2026-06-01

This migration adds support for passwordless email-based authentication
alongside existing Azure AD authentication. Includes email_login_tokens
table and updates to users table.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create email_login_tokens table
    op.create_table(
        "email_login_tokens",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("is_used", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_ip_address", sa.String(45), nullable=True),
        sa.Column("used_user_agent", sa.String(500), nullable=True),
        sa.Column("request_ip_address", sa.String(45), nullable=False),
        sa.Column("invalidation_reason", sa.String(100), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("idx_email_unused", "email_login_tokens", ["email", "is_used"])
    op.create_index("idx_token_hash", "email_login_tokens", ["token_hash"])
    op.create_index("idx_expires_at", "email_login_tokens", ["expires_at"])

    # Update users table to support email authentication
    op.add_column("users", sa.Column("auth_source", sa.String(20), nullable=True, server_default="azure_ad"))
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.add_column("users", sa.Column("last_login_method", sa.String(20), nullable=True))

    # Make oid nullable to support email-only users
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("oid", existing_type=sa.String(36), nullable=True)


def downgrade() -> None:
    # Restore oid to not nullable
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("oid", existing_type=sa.String(36), nullable=False)

    # Remove email_login columns
    op.drop_column("users", "last_login_method")
    op.drop_column("users", "email_verified")
    op.drop_column("users", "auth_source")

    # Drop email_login_tokens table
    op.drop_index("idx_expires_at", table_name="email_login_tokens")
    op.drop_index("idx_token_hash", table_name="email_login_tokens")
    op.drop_index("idx_email_unused", table_name="email_login_tokens")
    op.drop_table("email_login_tokens")
