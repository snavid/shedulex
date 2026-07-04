"""add user_email and user_name to audit_logs

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-04

"""
from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("audit_logs", sa.Column("user_email", sa.String(255), nullable=True))
    op.add_column("audit_logs", sa.Column("user_name", sa.String(200), nullable=True))
    op.create_index("ix_audit_logs_user_email", "audit_logs", ["user_email"])


def downgrade():
    op.drop_index("ix_audit_logs_user_email", table_name="audit_logs")
    op.drop_column("audit_logs", "user_name")
    op.drop_column("audit_logs", "user_email")
