"""add cancellation and scope fields to academic_events

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-05-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS academic_events (
            id VARCHAR(36) PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            event_type VARCHAR(50) DEFAULT 'event',
            start_datetime TIMESTAMPTZ NOT NULL,
            end_datetime TIMESTAMPTZ,
            all_day BOOLEAN DEFAULT FALSE,
            location VARCHAR(200),
            department_id VARCHAR(36),
            course_id VARCHAR(36),
            lecturer_id VARCHAR(36),
            created_by VARCHAR(36),
            is_public BOOLEAN DEFAULT TRUE,
            color VARCHAR(20) DEFAULT '#3B82F6',
            recurrence VARCHAR(50),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS academic_semesters (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            academic_year VARCHAR(20) NOT NULL,
            semester_number INTEGER NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            registration_start DATE,
            registration_end DATE,
            exam_start DATE,
            exam_end DATE,
            is_current BOOLEAN DEFAULT FALSE
        )
    """))

    op.execute(sa.text(
        "ALTER TABLE academic_events ADD COLUMN IF NOT EXISTS university_id VARCHAR(36)"
    ))
    op.execute(sa.text(
        "ALTER TABLE academic_events ADD COLUMN IF NOT EXISTS student_group_id VARCHAR(36)"
    ))
    op.execute(sa.text(
        "ALTER TABLE academic_events ADD COLUMN IF NOT EXISTS program_id VARCHAR(36)"
    ))
    op.execute(sa.text(
        "ALTER TABLE academic_events ADD COLUMN IF NOT EXISTS is_cancelled BOOLEAN DEFAULT FALSE"
    ))
    op.execute(sa.text(
        "ALTER TABLE academic_events ADD COLUMN IF NOT EXISTS cancelled_by VARCHAR(36)"
    ))
    op.execute(sa.text(
        "ALTER TABLE academic_events ADD COLUMN IF NOT EXISTS cancellation_reason VARCHAR(300)"
    ))


def downgrade():
    op.execute(sa.text(
        "ALTER TABLE academic_events DROP COLUMN IF EXISTS cancellation_reason"
    ))
    op.execute(sa.text(
        "ALTER TABLE academic_events DROP COLUMN IF EXISTS cancelled_by"
    ))
    op.execute(sa.text(
        "ALTER TABLE academic_events DROP COLUMN IF EXISTS is_cancelled"
    ))
    op.execute(sa.text(
        "ALTER TABLE academic_events DROP COLUMN IF EXISTS program_id"
    ))
    op.execute(sa.text(
        "ALTER TABLE academic_events DROP COLUMN IF EXISTS student_group_id"
    ))
    op.execute(sa.text(
        "ALTER TABLE academic_events DROP COLUMN IF EXISTS university_id"
    ))
