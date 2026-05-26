"""add university_id to audit_logs

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-05-24

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('audit_logs', sa.Column('university_id', sa.String(36), nullable=True))
    op.create_index('ix_audit_logs_university_id', 'audit_logs', ['university_id'])


def downgrade():
    op.drop_index('ix_audit_logs_university_id', table_name='audit_logs')
    op.drop_column('audit_logs', 'university_id')
