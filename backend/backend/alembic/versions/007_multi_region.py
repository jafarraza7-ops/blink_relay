"""change region column to JSON array for multi-region support

Revision ID: 007
Revises: 006
Create Date: 2026-05-26

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add a temp column to hold the new JSON array value
    with op.batch_alter_table('requests') as batch_op:
        batch_op.add_column(
            sa.Column('region_new', sa.Text, nullable=False, server_default='["NA"]')
        )

    # 2. Backfill: wrap each existing single-value region in a JSON array
    op.execute('UPDATE requests SET region_new = \'["\' || region || \'"]\'')

    # 3. Drop old column and rename new one
    with op.batch_alter_table('requests') as batch_op:
        batch_op.drop_column('region')
        batch_op.alter_column('region_new', new_column_name='region')


def downgrade() -> None:
    # 1. Add a temp column to hold the old single-value region
    with op.batch_alter_table('requests') as batch_op:
        batch_op.add_column(
            sa.Column('region_old', sa.String(10), nullable=False, server_default='NA')
        )

    # 2. Extract the first element from the JSON array
    op.execute("UPDATE requests SET region_old = json_extract(region, '$[0]')")

    # 3. Drop new column and restore old one
    with op.batch_alter_table('requests') as batch_op:
        batch_op.drop_column('region')
        batch_op.alter_column('region_old', new_column_name='region')
