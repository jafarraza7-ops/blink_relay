"""Add email groups for system notifications.

Revision ID: 017
Revises: 016
Create Date: 2026-06-08 15:30:00.000000

Creates email_groups and email_group_members tables for managing
distribution lists for bulk notifications (e.g., PM notifications).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '017'
down_revision = '016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create email_groups table
    op.create_table(
        'email_groups',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=254), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_email_groups_name'), 'email_groups', ['name'], unique=True)
    op.create_index(op.f('ix_email_groups_email'), 'email_groups', ['email'], unique=True)

    # Create email_group_members table
    op.create_table(
        'email_group_members',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('group_id', sa.Uuid(), nullable=False),
        sa.Column('user_email', sa.String(length=254), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['email_groups.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('group_id', 'user_email', name='unique_group_member')
    )
    op.create_index(op.f('ix_email_group_members_group_id'), 'email_group_members', ['group_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_email_group_members_group_id'), table_name='email_group_members')
    op.drop_table('email_group_members')
    op.drop_index(op.f('ix_email_groups_email'), table_name='email_groups')
    op.drop_index(op.f('ix_email_groups_name'), table_name='email_groups')
    op.drop_table('email_groups')
