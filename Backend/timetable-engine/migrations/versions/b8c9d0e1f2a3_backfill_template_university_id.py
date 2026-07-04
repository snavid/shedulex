"""backfill timetable_templates university_id

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-04

"""
from alembic import op
import sqlalchemy as sa

revision = 'b8c9d0e1f2a3'
down_revision = 'a7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade():
    # Single university: assign all orphaned templates to it.
    op.execute(sa.text("""
        UPDATE timetable_templates
        SET university_id = (
            SELECT id FROM universities ORDER BY created_at NULLS LAST, id LIMIT 1
        )
        WHERE university_id IS NULL
          AND (SELECT COUNT(*) FROM universities) = 1
    """))

    # Multiple universities: assign to the university with the most departments.
    op.execute(sa.text("""
        UPDATE timetable_templates
        SET university_id = sub.university_id
        FROM (
            SELECT d.university_id
            FROM departments d
            GROUP BY d.university_id
            ORDER BY COUNT(*) DESC, d.university_id
            LIMIT 1
        ) AS sub
        WHERE timetable_templates.university_id IS NULL
          AND (SELECT COUNT(*) FROM universities) > 1
    """))

    # Fallback: first university if still NULL (e.g. no departments yet).
    op.execute(sa.text("""
        UPDATE timetable_templates
        SET university_id = (
            SELECT id FROM universities ORDER BY created_at NULLS LAST, id LIMIT 1
        )
        WHERE university_id IS NULL
          AND EXISTS (SELECT 1 FROM universities)
    """))


def downgrade():
    pass
