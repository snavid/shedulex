#!/usr/bin/env python3
"""
Auth service user seeder — wipes all users (keeps roles) then creates
admin + timetable_officer + hod accounts for each of the 5 universities
seeded by timetable-engine/seed_fresh.py.

Run AFTER seed_fresh.py:
  docker compose exec auth-service python seed_users.py

Credentials (change in production!):
  admin:             admin@<code>.shedulex.ac  /  Admin@2026
  timetable_officer: officer@<code>.shedulex.ac / Officer@2026
  hod:               hod@<code>.shedulex.ac    /  Hod@2026
"""
import sys, os
import json
import urllib.request
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import text
from app import create_app
from app.extensions import db
from app.models.user import User, Role, UserSession
from app.services.auth_service import seed_roles

# ── Same deterministic IDs as seed_fresh.py ───────────────────────────────────
UNI_IDS = {
    "STR": "a0000001-0000-0000-0000-000000000001",
    "UON": "a0000001-0000-0000-0000-000000000002",
    "KU":  "a0000001-0000-0000-0000-000000000003",
    "MU":  "a0000001-0000-0000-0000-000000000004",
    "TUK": "a0000001-0000-0000-0000-000000000005",
}

UNI_NAMES = {
    "STR": "Strathmore University",
    "UON": "University of Nairobi",
    "KU":  "Kenyatta University",
    "MU":  "Moi University",
    "TUK": "Technical University of Kenya",
}

# ── Accounts to create per university ────────────────────────────────────────
# (role, first, last, email_prefix, username_prefix, password)
ACCOUNTS = [
    ("admin",            "Admin",   "User",    "admin",   "admin",   "Admin@2026"),
    ("timetable_officer","Officer", "User",    "officer", "officer", "Officer@2026"),
    ("hod",              "Head",    "Dept",    "hod",     "hod",     "Hod@2026"),
    ("lecturer",         "Lecturer","Demo",    "lect",    "lect",    "Lect@2026"),
]


def _fetch_first_department_id(university_id: str) -> str | None:
    timetable_url = os.environ.get("TIMETABLE_SERVICE_URL", "http://timetable-engine:5002")
    internal_key = os.environ.get("INTERNAL_SERVICE_KEY", "dev-internal-service-key")
    url = f"{timetable_url}/api/v1/departments?university_id={university_id}"
    req = urllib.request.Request(
        url,
        headers={"X-Internal-Service-Key": internal_key},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode())
            depts = body.get("data") or []
            return depts[0]["id"] if depts else None
    except Exception:
        return None


def wipe_users(session):
    print("  Wiping user sessions and users…")
    session.execute(text("DELETE FROM user_sessions"))
    session.execute(text("DELETE FROM users"))
    session.commit()
    print("  Done. (Redis token cache will expire naturally)")


def seed():
    app = create_app()
    with app.app_context():
        print("\n=== Auth Service User Seeder ===\n")

        wipe_users(db.session)

        # Ensure roles exist
        seed_roles()

        role_map = {r.name: r for r in Role.query.all()}

        created = 0
        phone_counter = 1
        for code, uni_id in UNI_IDS.items():
            code_lower = code.lower()
            dept_id = _fetch_first_department_id(uni_id)
            print(f"Creating accounts for {UNI_NAMES[code]} ({code})…")
            for role_name, first, last, email_pfx, uname_pfx, pwd in ACCOUNTS:
                role = role_map.get(role_name)
                if not role:
                    print(f"  WARNING: role '{role_name}' not found, skipping")
                    continue

                email    = f"{email_pfx}@{code_lower}.shedulex.ac"
                username = f"{uname_pfx}.{code_lower}"
                phone    = f"+255700000{phone_counter:03d}"
                phone_counter += 1

                user = User(
                    email=email,
                    username=username,
                    first_name=first,
                    last_name=f"{last} ({code})",
                    phone=phone,
                    university_id=uni_id,
                    department_id=dept_id if role_name == "hod" and dept_id else None,
                    role_id=role.id,
                    is_active=True,
                    is_approved=True,
                    is_verified=True,
                    must_change_password=False,
                )
                user.set_password(pwd)
                db.session.add(user)
                created += 1

        db.session.commit()

        print(f"\n=== Done. Created {created} users. ===\n")
        print("Login credentials:")
        print(f"  {'University':<40} {'Email':<40} {'Password'}")
        print(f"  {'-'*40} {'-'*40} {'-'*20}")
        for code in UNI_IDS:
            code_lower = code.lower()
            for role_name, _, _, email_pfx, _, pwd in ACCOUNTS:
                email = f"{email_pfx}@{code_lower}.shedulex.ac"
                print(f"  {UNI_NAMES[code]:<40} {email:<40} {pwd}")
        print()
        print("Note: All admin accounts are immediately active.")
        print("      Log in with any admin account to explore that university's data.")


if __name__ == "__main__":
    seed()
