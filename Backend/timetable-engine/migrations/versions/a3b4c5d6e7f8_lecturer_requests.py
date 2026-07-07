"""add lecturer_requests table

Revision ID: a3b4c5d6e7f8
Revises: b8c9d0e1f2a3
Create Date: 2026-07-06

"""
from alembic import op
import sqlalchemy as sa

revision = 'a3b4c5d6e7f8'
down_revision = 'b8c9d0e1f2a3'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS lecturer_requests (
            id                 VARCHAR(36) PRIMARY KEY,
            lecturer_user_id   VARCHAR(36) NOT NULL,
            lecturer_name      VARCHAR(200),
            department_id      VARCHAR(36) NOT NULL REFERENCES departments(id),
            category           VARCHAR(30) NOT NULL,
            message            VARCHAR(1000) NOT NULL,
            status             VARCHAR(20) NOT NULL DEFAULT 'pending_hod',
            hod_decided_by     VARCHAR(36),
            hod_decided_at     TIMESTAMPTZ,
            hod_note           VARCHAR(500),
            admin_decided_by   VARCHAR(36),
            admin_decided_at   TIMESTAMPTZ,
            admin_note         VARCHAR(500),
            created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_lecturer_requests_status ON lecturer_requests(status)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_lecturer_requests_department_id ON lecturer_requests(department_id)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_lecturer_requests_lecturer_user_id ON lecturer_requests(lecturer_user_id)"))


def downgrade():
    op.execute(sa.text("DROP TABLE IF EXISTS lecturer_requests"))
