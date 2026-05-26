"""add academic_years table and timetables.academic_year_id

Revision ID: d3e4f5a6b7c8
Revises: c1d2e3f4g5h6
Create Date: 2026-05-24 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'd3e4f5a6b7c8'
down_revision = 'c1d2e3f4g5h6'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS academic_years (
            id              VARCHAR(36)  NOT NULL PRIMARY KEY,
            name            VARCHAR(20)  NOT NULL,
            university_id   VARCHAR(36)  NOT NULL REFERENCES universities(id) ON DELETE CASCADE,
            sem1_start      DATE,
            sem1_end        DATE,
            sem2_start      DATE,
            sem2_end        DATE,
            is_current      BOOLEAN      NOT NULL DEFAULT FALSE,
            status          VARCHAR(20)  NOT NULL DEFAULT 'active',
            created_at      TIMESTAMPTZ  DEFAULT NOW(),
            CONSTRAINT uq_academic_year_uni UNIQUE (name, university_id)
        )
    """))
    op.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS ix_academic_years_university_id
        ON academic_years (university_id)
    """))
    op.execute(sa.text("""
        ALTER TABLE timetables
        ADD COLUMN IF NOT EXISTS academic_year_id VARCHAR(36)
            REFERENCES academic_years(id) ON DELETE SET NULL
    """))
    op.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS ix_timetables_academic_year_id
        ON timetables (academic_year_id)
    """))


def downgrade():
    op.execute(sa.text("ALTER TABLE timetables DROP COLUMN IF EXISTS academic_year_id"))
    op.execute(sa.text("DROP TABLE IF EXISTS academic_years"))
