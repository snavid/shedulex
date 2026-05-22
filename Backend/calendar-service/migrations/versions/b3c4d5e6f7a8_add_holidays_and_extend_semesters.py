"""add academic_holidays, extend academic_semesters and academic_events

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-05-22 14:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'b3c4d5e6f7a8'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # ── AcademicHoliday table ────────────────────────────────────────────────
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS academic_holidays (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            date DATE NOT NULL,
            end_date DATE,
            holiday_type VARCHAR(50) DEFAULT 'public',
            university_id VARCHAR(36),
            country_code VARCHAR(5),
            is_recurring BOOLEAN DEFAULT FALSE,
            created_by VARCHAR(36),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))

    # ── academic_semesters extensions ────────────────────────────────────────
    op.execute(sa.text(
        "ALTER TABLE academic_semesters ADD COLUMN IF NOT EXISTS break_start DATE"
    ))
    op.execute(sa.text(
        "ALTER TABLE academic_semesters ADD COLUMN IF NOT EXISTS break_end DATE"
    ))
    op.execute(sa.text(
        "ALTER TABLE academic_semesters ADD COLUMN IF NOT EXISTS university_id VARCHAR(36)"
    ))
    op.execute(sa.text(
        "ALTER TABLE academic_semesters ADD COLUMN IF NOT EXISTS timezone VARCHAR(60) DEFAULT 'UTC'"
    ))
    op.execute(sa.text(
        "ALTER TABLE academic_semesters ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()"
    ))
    op.execute(sa.text(
        "ALTER TABLE academic_semesters ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()"
    ))

    # ── academic_events extensions ───────────────────────────────────────────
    op.execute(sa.text(
        "ALTER TABLE academic_events ADD COLUMN IF NOT EXISTS affects_timetable BOOLEAN DEFAULT FALSE"
    ))
    op.execute(sa.text(
        "ALTER TABLE academic_events ADD COLUMN IF NOT EXISTS timetable_scope VARCHAR(50)"
    ))


def downgrade():
    op.execute(sa.text(
        "ALTER TABLE academic_events DROP COLUMN IF EXISTS timetable_scope"
    ))
    op.execute(sa.text(
        "ALTER TABLE academic_events DROP COLUMN IF EXISTS affects_timetable"
    ))
    op.execute(sa.text(
        "ALTER TABLE academic_semesters DROP COLUMN IF EXISTS updated_at"
    ))
    op.execute(sa.text(
        "ALTER TABLE academic_semesters DROP COLUMN IF EXISTS created_at"
    ))
    op.execute(sa.text(
        "ALTER TABLE academic_semesters DROP COLUMN IF EXISTS timezone"
    ))
    op.execute(sa.text(
        "ALTER TABLE academic_semesters DROP COLUMN IF EXISTS university_id"
    ))
    op.execute(sa.text(
        "ALTER TABLE academic_semesters DROP COLUMN IF EXISTS break_end"
    ))
    op.execute(sa.text(
        "ALTER TABLE academic_semesters DROP COLUMN IF EXISTS break_start"
    ))
    op.execute(sa.text("DROP TABLE IF EXISTS academic_holidays"))
