"""add university_id to rooms

Revision ID: e5f6a7b8c9d0
Revises: d3e4f5a6b7c8
Create Date: 2026-05-24

"""
from alembic import op
import sqlalchemy as sa

revision = 'e5f6a7b8c9d0'
down_revision = 'd3e4f5a6b7c8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('rooms', sa.Column(
        'university_id',
        sa.String(36),
        sa.ForeignKey('universities.id'),
        nullable=True,
    ))
    op.create_index('ix_rooms_university_id', 'rooms', ['university_id'])


def downgrade():
    op.drop_index('ix_rooms_university_id', table_name='rooms')
    op.drop_column('rooms', 'university_id')
