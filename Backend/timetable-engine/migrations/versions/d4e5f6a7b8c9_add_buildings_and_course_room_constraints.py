"""add buildings table, rooms.building_id, courses.required_room_type/fixed_room_id

Revision ID: d4e5f6a7b8c9
Revises: a3b4c5d6e7f8
Create Date: 2026-07-06

"""
from alembic import op
import sqlalchemy as sa
import uuid

revision = 'd4e5f6a7b8c9'
down_revision = 'a3b4c5d6e7f8'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS buildings (
            id             VARCHAR(36) PRIMARY KEY,
            name           VARCHAR(150) NOT NULL,
            code           VARCHAR(20),
            university_id  VARCHAR(36) REFERENCES universities(id),
            address        VARCHAR(300),
            created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_buildings_university_id ON buildings(university_id)"
    ))

    op.execute(sa.text(
        "ALTER TABLE rooms ADD COLUMN IF NOT EXISTS building_id VARCHAR(36) "
        "REFERENCES buildings(id) ON DELETE SET NULL"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_rooms_building_id ON rooms(building_id)"
    ))

    op.execute(sa.text(
        "ALTER TABLE courses ADD COLUMN IF NOT EXISTS required_room_type VARCHAR(50)"
    ))
    op.execute(sa.text(
        "ALTER TABLE courses ADD COLUMN IF NOT EXISTS fixed_room_id VARCHAR(36) "
        "REFERENCES rooms(id) ON DELETE SET NULL"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_courses_fixed_room_id ON courses(fixed_room_id)"
    ))
    op.execute(sa.text(
        "UPDATE courses SET required_room_type = 'lab' WHERE requires_lab = TRUE "
        "AND required_room_type IS NULL"
    ))

    # Backfill Building rows from distinct Room.building strings, then point
    # rooms.building_id at them. Done in Python (not pure SQL) since this repo
    # has no precedent for/guaranteed availability of an in-SQL UUID generator
    # (no pgcrypto/uuid-ossp usage anywhere in prior migrations). Idempotent:
    # safe to re-run, matching this repo's IF NOT EXISTS migration convention.
    conn = op.get_bind()
    pairs = conn.execute(sa.text(
        "SELECT DISTINCT building, university_id FROM rooms "
        "WHERE building IS NOT NULL AND building <> ''"
    )).fetchall()
    for building_name, uni_id in pairs:
        existing = conn.execute(
            sa.text(
                "SELECT id FROM buildings WHERE name = :name "
                "AND university_id IS NOT DISTINCT FROM :uni"
            ),
            {"name": building_name, "uni": uni_id},
        ).fetchone()
        bid = existing[0] if existing else str(uuid.uuid4())
        if not existing:
            conn.execute(
                sa.text(
                    "INSERT INTO buildings (id, name, code, university_id) "
                    "VALUES (:id, :name, :code, :uni)"
                ),
                {
                    "id": bid,
                    "name": building_name,
                    "code": building_name[:20].upper().replace(" ", "")[:20],
                    "uni": uni_id,
                },
            )
        conn.execute(
            sa.text(
                "UPDATE rooms SET building_id = :bid WHERE building = :name "
                "AND university_id IS NOT DISTINCT FROM :uni AND building_id IS NULL"
            ),
            {"bid": bid, "name": building_name, "uni": uni_id},
        )


def downgrade():
    op.execute(sa.text("DROP INDEX IF EXISTS ix_courses_fixed_room_id"))
    op.execute(sa.text("ALTER TABLE courses DROP COLUMN IF EXISTS fixed_room_id"))
    op.execute(sa.text("ALTER TABLE courses DROP COLUMN IF EXISTS required_room_type"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_rooms_building_id"))
    op.execute(sa.text("ALTER TABLE rooms DROP COLUMN IF EXISTS building_id"))
    op.execute(sa.text("DROP TABLE IF EXISTS buildings"))
