"""add enrollment fields to users

Revision ID: d5e6f7a8b9c0
Revises: b1c2d3e4f5a6
Create Date: 2026-07-03 20:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "d5e6f7a8b9c0"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("department_id", sa.String(length=36), nullable=True))
    op.add_column("users", sa.Column("program_id", sa.String(length=36), nullable=True))
    op.add_column("users", sa.Column("student_group_id", sa.String(length=36), nullable=True))


def downgrade():
    op.drop_column("users", "student_group_id")
    op.drop_column("users", "program_id")
    op.drop_column("users", "department_id")
