"""initial

Revision ID: c4f06105187a
Revises:
Create Date: 2026-05-22 10:34:29.495178

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4f06105187a'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Idempotent: safe to run on both fresh installs and existing DBs.
    op.execute(sa.text(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS university_id VARCHAR(36)"
    ))
    op.execute(sa.text(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT FALSE"
    ))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('must_change_password')
        batch_op.drop_column('university_id')
