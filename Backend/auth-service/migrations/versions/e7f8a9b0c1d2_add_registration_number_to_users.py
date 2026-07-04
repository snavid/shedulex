"""add registration_number to users

Revision ID: e7f8a9b0c1d2
Revises: d5e6f7a8b9c0
Create Date: 2026-07-04 00:30:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "e7f8a9b0c1d2"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("registration_number", sa.String(length=50), nullable=True))
    op.create_index("ix_users_registration_number", "users", ["registration_number"], unique=False)
    op.create_unique_constraint("uq_user_uni_reg_number", "users", ["university_id", "registration_number"])


def downgrade():
    op.drop_constraint("uq_user_uni_reg_number", "users", type_="unique")
    op.drop_index("ix_users_registration_number", table_name="users")
    op.drop_column("users", "registration_number")
