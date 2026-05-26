"""add is_approved to users

Revision ID: b1c2d3e4f5a6
Revises: c4f06105187a
Create Date: 2026-05-24 14:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'b1c2d3e4f5a6'
down_revision = 'c4f06105187a'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column(
        'is_approved', sa.Boolean(), nullable=False, server_default='1'
    ))


def downgrade():
    op.drop_column('users', 'is_approved')
