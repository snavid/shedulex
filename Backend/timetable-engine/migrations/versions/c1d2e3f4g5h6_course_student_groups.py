"""add course_student_groups join table

Revision ID: c1d2e3f4g5h6
Revises: b2c3d4e5f6a7
Create Date: 2026-05-24 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'c1d2e3f4g5h6'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS course_student_groups (
            course_id VARCHAR(36) NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
            student_group_id VARCHAR(36) NOT NULL REFERENCES student_groups(id) ON DELETE CASCADE,
            PRIMARY KEY (course_id, student_group_id)
        )
    """))
    op.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS ix_csg_course_id ON course_student_groups (course_id)
    """))
    op.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS ix_csg_student_group_id ON course_student_groups (student_group_id)
    """))


def downgrade():
    op.execute(sa.text("DROP TABLE IF EXISTS course_student_groups"))
