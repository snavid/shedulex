"""add course_group_lecturers table

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-05-26

"""
from alembic import op
import sqlalchemy as sa

revision = 'f1a2b3c4d5e6'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS course_group_lecturers (
            course_id        VARCHAR(36) NOT NULL
                REFERENCES courses(id) ON DELETE CASCADE,
            student_group_id VARCHAR(36) NOT NULL
                REFERENCES student_groups(id) ON DELETE CASCADE,
            lecturer_id      VARCHAR(36)
                REFERENCES lecturers(id) ON DELETE SET NULL,
            PRIMARY KEY (course_id, student_group_id)
        )
    """))


def downgrade():
    op.execute(sa.text("DROP TABLE IF EXISTS course_group_lecturers"))
