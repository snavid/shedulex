"""add timetable templates, extend time_slots, constraints, and lecturers

Revision ID: b2c3d4e5f6a7
Revises: f4c57f6ce5eb
Create Date: 2026-05-22 14:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = 'f4c57f6ce5eb'
branch_labels = None
depends_on = None


def upgrade():
    # ── TimetableTemplate ────────────────────────────────────────────────────
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS timetable_templates (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            description VARCHAR(500),
            university_id VARCHAR(36),
            is_default BOOLEAN DEFAULT FALSE,
            days_of_week JSON,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))

    # ── TemplateTimeBlock ────────────────────────────────────────────────────
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS template_time_blocks (
            id VARCHAR(36) PRIMARY KEY,
            template_id VARCHAR(36) NOT NULL REFERENCES timetable_templates(id) ON DELETE CASCADE,
            label VARCHAR(100) NOT NULL,
            start_time VARCHAR(10) NOT NULL,
            end_time VARCHAR(10) NOT NULL,
            block_type VARCHAR(20) DEFAULT 'class',
            sort_order INTEGER DEFAULT 0
        )
    """))

    # ── time_slots extensions ────────────────────────────────────────────────
    op.execute(sa.text(
        "ALTER TABLE time_slots ADD COLUMN IF NOT EXISTS slot_type VARCHAR(20) DEFAULT 'class'"
    ))
    op.execute(sa.text(
        "ALTER TABLE time_slots ADD COLUMN IF NOT EXISTS label VARCHAR(100)"
    ))
    op.execute(sa.text(
        "ALTER TABLE time_slots ADD COLUMN IF NOT EXISTS template_id VARCHAR(36)"
        " REFERENCES timetable_templates(id) ON DELETE SET NULL"
    ))

    # ── timetables extensions ────────────────────────────────────────────────
    op.execute(sa.text(
        "ALTER TABLE timetables ADD COLUMN IF NOT EXISTS template_id VARCHAR(36)"
        " REFERENCES timetable_templates(id) ON DELETE SET NULL"
    ))
    op.execute(sa.text(
        "ALTER TABLE timetables ADD COLUMN IF NOT EXISTS calendar_semester_id VARCHAR(36)"
    ))
    op.execute(sa.text(
        "ALTER TABLE timetables ADD COLUMN IF NOT EXISTS violation_report JSON"
    ))

    # ── constraints extensions ───────────────────────────────────────────────
    op.execute(sa.text(
        "ALTER TABLE constraints ADD COLUMN IF NOT EXISTS rule_type VARCHAR(100)"
    ))
    op.execute(sa.text(
        "ALTER TABLE constraints ADD COLUMN IF NOT EXISTS entity_type VARCHAR(50)"
    ))
    op.execute(sa.text(
        "ALTER TABLE constraints ADD COLUMN IF NOT EXISTS entity_id VARCHAR(36)"
    ))
    op.execute(sa.text(
        "ALTER TABLE constraints ADD COLUMN IF NOT EXISTS university_id VARCHAR(36)"
    ))
    op.execute(sa.text(
        "ALTER TABLE constraints ADD COLUMN IF NOT EXISTS department_id VARCHAR(36)"
        " REFERENCES departments(id) ON DELETE SET NULL"
    ))

    # ── lecturers extensions ─────────────────────────────────────────────────
    op.execute(sa.text(
        "ALTER TABLE lecturers ADD COLUMN IF NOT EXISTS max_hours_per_day INTEGER DEFAULT 6"
    ))
    op.execute(sa.text(
        "ALTER TABLE lecturers ADD COLUMN IF NOT EXISTS max_consecutive_hours INTEGER DEFAULT 3"
    ))
    op.execute(sa.text(
        "ALTER TABLE lecturers ADD COLUMN IF NOT EXISTS preferred_days JSON"
    ))
    op.execute(sa.text(
        "ALTER TABLE lecturers ADD COLUMN IF NOT EXISTS unavailable_slots JSON"
    ))

    # Backfill slot_type from is_break
    op.execute(sa.text("""
        UPDATE time_slots
        SET slot_type = 'break'
        WHERE is_break = TRUE AND slot_type = 'class'
    """))


def downgrade():
    op.execute(sa.text("ALTER TABLE lecturers DROP COLUMN IF EXISTS unavailable_slots"))
    op.execute(sa.text("ALTER TABLE lecturers DROP COLUMN IF EXISTS preferred_days"))
    op.execute(sa.text("ALTER TABLE lecturers DROP COLUMN IF EXISTS max_consecutive_hours"))
    op.execute(sa.text("ALTER TABLE lecturers DROP COLUMN IF EXISTS max_hours_per_day"))
    op.execute(sa.text("ALTER TABLE constraints DROP COLUMN IF EXISTS department_id"))
    op.execute(sa.text("ALTER TABLE constraints DROP COLUMN IF EXISTS university_id"))
    op.execute(sa.text("ALTER TABLE constraints DROP COLUMN IF EXISTS entity_id"))
    op.execute(sa.text("ALTER TABLE constraints DROP COLUMN IF EXISTS entity_type"))
    op.execute(sa.text("ALTER TABLE constraints DROP COLUMN IF EXISTS rule_type"))
    op.execute(sa.text("ALTER TABLE timetables DROP COLUMN IF EXISTS violation_report"))
    op.execute(sa.text("ALTER TABLE timetables DROP COLUMN IF EXISTS calendar_semester_id"))
    op.execute(sa.text("ALTER TABLE timetables DROP COLUMN IF EXISTS template_id"))
    op.execute(sa.text("ALTER TABLE time_slots DROP COLUMN IF EXISTS template_id"))
    op.execute(sa.text("ALTER TABLE time_slots DROP COLUMN IF EXISTS label"))
    op.execute(sa.text("ALTER TABLE time_slots DROP COLUMN IF EXISTS slot_type"))
    op.execute(sa.text("DROP TABLE IF EXISTS template_time_blocks"))
    op.execute(sa.text("DROP TABLE IF EXISTS timetable_templates"))
