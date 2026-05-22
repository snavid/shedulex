"""initial

Revision ID: f4c57f6ce5eb
Revises:
Create Date: 2026-05-22 10:34:31.356009

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f4c57f6ce5eb'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Idempotent: safe to run on both fresh installs and existing DBs.
    # Uses IF NOT EXISTS / IF EXISTS / DO blocks throughout so re-running is harmless.

    # ── New tables (created by db.create_all on startup, but included here for
    #    completeness so the migration is self-contained) ──────────────────────
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS universities (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(200) NOT NULL UNIQUE,
            code VARCHAR(20) NOT NULL UNIQUE,
            address VARCHAR(300),
            website VARCHAR(255),
            logo_url VARCHAR(500),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS programs (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            code VARCHAR(20) NOT NULL,
            department_id VARCHAR(36) NOT NULL REFERENCES departments(id),
            academic_level VARCHAR(50) NOT NULL DEFAULT 'Bachelor',
            duration_years INTEGER DEFAULT 3,
            description VARCHAR(500),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_program_code_dept UNIQUE (code, department_id)
        )
    """))

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS student_groups (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(150) NOT NULL,
            code VARCHAR(20) NOT NULL,
            program_id VARCHAR(36) NOT NULL REFERENCES programs(id),
            year_of_study INTEGER NOT NULL DEFAULT 1,
            semester INTEGER NOT NULL DEFAULT 1,
            student_count INTEGER DEFAULT 30,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS lecturer_programs (
            lecturer_id VARCHAR(36) NOT NULL REFERENCES lecturers(id),
            program_id VARCHAR(36) NOT NULL REFERENCES programs(id),
            PRIMARY KEY (lecturer_id, program_id)
        )
    """))

    # ── Columns on existing tables ────────────────────────────────────────────
    op.execute(sa.text(
        "ALTER TABLE departments ADD COLUMN IF NOT EXISTS university_id VARCHAR(36)"
    ))
    op.execute(sa.text(
        "ALTER TABLE lecturers ADD COLUMN IF NOT EXISTS phone VARCHAR(20)"
    ))
    op.execute(sa.text(
        "ALTER TABLE courses ADD COLUMN IF NOT EXISTS program_id VARCHAR(36)"
    ))
    op.execute(sa.text(
        "ALTER TABLE timetables ADD COLUMN IF NOT EXISTS program_id VARCHAR(36)"
    ))
    op.execute(sa.text(
        "ALTER TABLE timetable_entries ADD COLUMN IF NOT EXISTS student_group_id VARCHAR(36)"
    ))

    # ── Constraint changes on departments ─────────────────────────────────────
    # Drop old per-column unique constraints (were present in old schema).
    op.execute(sa.text(
        "ALTER TABLE departments DROP CONSTRAINT IF EXISTS departments_code_key"
    ))
    op.execute(sa.text(
        "ALTER TABLE departments DROP CONSTRAINT IF EXISTS departments_name_key"
    ))
    # Add new composite unique constraint (idempotent via DO block).
    op.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_dept_code_university'
            ) THEN
                ALTER TABLE departments
                    ADD CONSTRAINT uq_dept_code_university UNIQUE (code, university_id);
            END IF;
        END $$;
    """))

    # ── Foreign key from departments.university_id → universities ────────────
    op.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'departments'::regclass
                  AND conname = 'departments_university_id_fkey'
            ) THEN
                ALTER TABLE departments
                    ADD CONSTRAINT departments_university_id_fkey
                    FOREIGN KEY (university_id) REFERENCES universities(id);
            END IF;
        EXCEPTION WHEN others THEN NULL;
        END $$;
    """))

    # ── Foreign key from courses.program_id → programs ───────────────────────
    op.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'courses'::regclass
                  AND conname = 'courses_program_id_fkey'
            ) THEN
                ALTER TABLE courses
                    ADD CONSTRAINT courses_program_id_fkey
                    FOREIGN KEY (program_id) REFERENCES programs(id);
            END IF;
        EXCEPTION WHEN others THEN NULL;
        END $$;
    """))

    # ── Foreign key from timetables.program_id → programs ────────────────────
    op.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'timetables'::regclass
                  AND conname = 'timetables_program_id_fkey'
            ) THEN
                ALTER TABLE timetables
                    ADD CONSTRAINT timetables_program_id_fkey
                    FOREIGN KEY (program_id) REFERENCES programs(id);
            END IF;
        EXCEPTION WHEN others THEN NULL;
        END $$;
    """))

    # ── Foreign key from timetable_entries.student_group_id → student_groups ─
    op.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'timetable_entries'::regclass
                  AND conname = 'timetable_entries_student_group_id_fkey'
            ) THEN
                ALTER TABLE timetable_entries
                    ADD CONSTRAINT timetable_entries_student_group_id_fkey
                    FOREIGN KEY (student_group_id) REFERENCES student_groups(id);
            END IF;
        EXCEPTION WHEN others THEN NULL;
        END $$;
    """))


def downgrade():
    op.execute(sa.text(
        "ALTER TABLE timetable_entries DROP CONSTRAINT IF EXISTS timetable_entries_student_group_id_fkey"
    ))
    op.execute(sa.text(
        "ALTER TABLE timetables DROP CONSTRAINT IF EXISTS timetables_program_id_fkey"
    ))
    op.execute(sa.text(
        "ALTER TABLE courses DROP CONSTRAINT IF EXISTS courses_program_id_fkey"
    ))
    op.execute(sa.text(
        "ALTER TABLE departments DROP CONSTRAINT IF EXISTS departments_university_id_fkey"
    ))
    op.execute(sa.text(
        "ALTER TABLE departments DROP CONSTRAINT IF EXISTS uq_dept_code_university"
    ))

    with op.batch_alter_table('timetable_entries', schema=None) as batch_op:
        batch_op.drop_column('student_group_id')

    with op.batch_alter_table('timetables', schema=None) as batch_op:
        batch_op.drop_column('program_id')

    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.drop_column('program_id')

    with op.batch_alter_table('lecturers', schema=None) as batch_op:
        batch_op.drop_column('phone')

    with op.batch_alter_table('departments', schema=None) as batch_op:
        batch_op.drop_column('university_id')

    op.drop_table('lecturer_programs')
    op.drop_table('student_groups')
    op.drop_table('programs')
    op.drop_table('universities')
