"""timetable_comments cascade delete FKs

Revision ID: a7b8c9d0e1f2
Revises: f1a2b3c4d5e6
Create Date: 2026-07-04

"""
from alembic import op
import sqlalchemy as sa

revision = 'a7b8c9d0e1f2'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS timetable_comments (
            id                  VARCHAR(36) PRIMARY KEY,
            entry_id            VARCHAR(36) NOT NULL,
            timetable_id        VARCHAR(36) NOT NULL,
            student_user_id     VARCHAR(36) NOT NULL,
            registration_number VARCHAR(50),
            student_name        VARCHAR(200),
            body                VARCHAR(500) NOT NULL,
            status              VARCHAR(20) DEFAULT 'visible',
            admin_reply         VARCHAR(500),
            created_at          TIMESTAMPTZ
        )
    """))

    op.execute(sa.text(
        "ALTER TABLE timetable_comments DROP CONSTRAINT IF EXISTS timetable_comments_entry_id_fkey"
    ))
    op.execute(sa.text(
        "ALTER TABLE timetable_comments DROP CONSTRAINT IF EXISTS timetable_comments_timetable_id_fkey"
    ))

    op.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'timetable_comments'::regclass
                  AND conname = 'timetable_comments_entry_id_fkey'
            ) THEN
                ALTER TABLE timetable_comments
                    ADD CONSTRAINT timetable_comments_entry_id_fkey
                    FOREIGN KEY (entry_id) REFERENCES timetable_entries(id) ON DELETE CASCADE;
            END IF;
        EXCEPTION WHEN others THEN NULL;
        END $$;
    """))

    op.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'timetable_comments'::regclass
                  AND conname = 'timetable_comments_timetable_id_fkey'
            ) THEN
                ALTER TABLE timetable_comments
                    ADD CONSTRAINT timetable_comments_timetable_id_fkey
                    FOREIGN KEY (timetable_id) REFERENCES timetables(id) ON DELETE CASCADE;
            END IF;
        EXCEPTION WHEN others THEN NULL;
        END $$;
    """))

    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_timetable_comments_entry_id ON timetable_comments (entry_id)"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_timetable_comments_timetable_id ON timetable_comments (timetable_id)"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_timetable_comments_student_user_id ON timetable_comments (student_user_id)"
    ))


def downgrade():
    op.execute(sa.text(
        "ALTER TABLE timetable_comments DROP CONSTRAINT IF EXISTS timetable_comments_entry_id_fkey"
    ))
    op.execute(sa.text(
        "ALTER TABLE timetable_comments DROP CONSTRAINT IF EXISTS timetable_comments_timetable_id_fkey"
    ))

    op.execute(sa.text("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'timetable_comments'
            ) THEN
                ALTER TABLE timetable_comments
                    ADD CONSTRAINT timetable_comments_entry_id_fkey
                    FOREIGN KEY (entry_id) REFERENCES timetable_entries(id);
                ALTER TABLE timetable_comments
                    ADD CONSTRAINT timetable_comments_timetable_id_fkey
                    FOREIGN KEY (timetable_id) REFERENCES timetables(id);
            END IF;
        EXCEPTION WHEN others THEN NULL;
        END $$;
    """))
