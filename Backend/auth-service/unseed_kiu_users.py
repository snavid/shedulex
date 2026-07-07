#!/usr/bin/env python3
"""
Deletes ONLY users belonging to Kampala International University (scoped
strictly to university_id = UNI_ID below). Does NOT touch any other
university's users — unlike seed_users.py, this never wipes the whole
users table.

Run BEFORE re-running seed_kiu_users.py if you want a clean slate:
  docker compose exec auth-service python unseed_kiu_users.py
  docker compose exec auth-service python seed_kiu_users.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import text
from app import create_app
from app.extensions import db

UNI_ID = "b0000001-0000-0000-0000-000000000001"  # must match seed_kiu.py / seed_kiu_users.py


def unseed():
    app = create_app()
    with app.app_context():
        params = {"uni": UNI_ID}
        print("\n=== Deleting Kampala International University users ===\n")

        user_ids = [r[0] for r in db.session.execute(
            text("SELECT id FROM users WHERE university_id = :uni"), params
        ).fetchall()]
        print(f"  Users found: {len(user_ids)}")

        db.session.execute(
            text("DELETE FROM user_sessions WHERE user_id = ANY(:uids)"),
            {"uids": user_ids or [None]},
        )
        db.session.execute(text("DELETE FROM users WHERE university_id = :uni"), params)
        db.session.commit()

        print("\n=== Done. KIU users removed. Other universities' users were not touched. ===\n")
        print("Next: docker compose exec auth-service python seed_kiu_users.py")


if __name__ == "__main__":
    unseed()
