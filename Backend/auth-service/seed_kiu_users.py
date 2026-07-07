#!/usr/bin/env python3
"""
Kampala International University user seeder — ADDITIVE ONLY.

Creates the standard admin/timetable_officer/hod/lecturer demo logins for
Kampala International University (matching seed_users.py's login pattern),
plus real `lecturer`-role accounts for one lecturer per department, with
Lecturer.user_id wired back to the timetable-engine record so the Lecturer
Portal can be exercised against real KIU data.

Unlike seed_users.py, this NEVER wipes existing users — every account is
created idempotently (skipped if the email already exists), safe to re-run.

Run AFTER seed_kiu.py:
  docker compose exec auth-service python seed_kiu_users.py
"""
import sys, os
import json
import urllib.request
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db
from app.models.user import User, Role
from app.services.auth_service import seed_roles

# ── Same deterministic ID as seed_kiu.py ───────────────────────────────────────
UNI_ID = "b0000001-0000-0000-0000-000000000001"
UNI_CODE = "kiu"

ACCOUNTS = [
    ("admin",             "Admin",   "User", "admin",   "admin",   "Admin@2026"),
    ("timetable_officer", "Officer", "User", "officer", "officer", "Officer@2026"),
    ("hod",               "Head",    "Dept", "hod",     "hod",     "Hod@2026"),
    ("lecturer",          "Lecturer","Demo", "lect",    "lect",    "Lect@2026"),
]


def _internal_headers():
    return {"X-Internal-Service-Key": os.environ.get("INTERNAL_SERVICE_KEY", "dev-internal-service-key")}


def _timetable_get(path):
    url = os.environ.get("TIMETABLE_SERVICE_URL", "http://timetable-engine:5002") + path
    req = urllib.request.Request(url, headers=_internal_headers())
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        print(f"  WARNING: GET {path} failed: {exc}")
        return {}


def _timetable_patch(path, payload):
    url = os.environ.get("TIMETABLE_SERVICE_URL", "http://timetable-engine:5002") + path
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, method="PUT",
        headers={**_internal_headers(), "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        print(f"  WARNING: PUT {path} failed: {exc}")
        return {}


def _slugify(name: str) -> str:
    slug = name.lower()
    for prefix in ("dr.", "prof.", "mr.", "ms."):
        slug = slug.replace(prefix, "")
    return "".join(ch for ch in slug if ch.isalnum() or ch == " ").strip().replace(" ", ".")


def _get_or_skip_user(email: str, **fields) -> tuple["User | None", bool]:
    """Create a User if the email doesn't already exist. Never overwrites."""
    existing = User.query.filter_by(email=email).first()
    if existing:
        return existing, False
    user = User(email=email, **fields)
    db.session.add(user)
    db.session.flush()
    return user, True


def seed():
    app = create_app()
    with app.app_context():
        print("\n=== Kampala International University User Seeder (additive) ===\n")

        seed_roles()
        role_map = {r.name: r for r in Role.query.all()}

        depts = _timetable_get(f"/api/v1/departments?university_id={UNI_ID}").get("data") or []
        first_dept_id = depts[0]["id"] if depts else None
        print(f"Found {len(depts)} KIU departments via internal API.")

        # ── Standard demo logins ─────────────────────────────────────────────
        created = 0
        for account_idx, (role_name, first, last, email_pfx, uname_pfx, pwd) in enumerate(ACCOUNTS, start=1):
            role = role_map.get(role_name)
            if not role:
                print(f"  WARNING: role '{role_name}' not found, skipping")
                continue
            email = f"{email_pfx}@{UNI_CODE}.shedulex.ac"
            user, was_created = _get_or_skip_user(
                email,
                username=f"{uname_pfx}.{UNI_CODE}",
                first_name=first, last_name=f"{last} (KIU)",
                phone=f"+256700900{account_idx:03d}",
                university_id=UNI_ID,
                department_id=first_dept_id if role_name == "hod" else None,
                role_id=role.id, is_active=True, is_approved=True,
                is_verified=True, must_change_password=False,
            )
            if was_created:
                user.set_password(pwd)
                created += 1
        db.session.commit()
        print(f"Created {created} standard demo login(s) (existing ones left untouched).")

        # ── One real lecturer account per department, wired to Lecturer.user_id ──
        lecturer_role = role_map.get("lecturer")
        lecturers = _timetable_get(f"/api/v1/lecturers?university_id={UNI_ID}").get("data") or []
        print(f"Found {len(lecturers)} KIU lecturers via internal API.")

        seen_departments = set()
        wired = 0
        phone_counter = 100
        for lect in lecturers:
            dept = lect.get("department") or {}
            dept_id = dept.get("id")
            if not dept_id or dept_id in seen_departments:
                continue
            if lect.get("user_id"):
                seen_departments.add(dept_id)
                continue
            seen_departments.add(dept_id)

            slug = _slugify(lect["name"])
            email = f"{slug}@{UNI_CODE}.shedulex.ac"
            # Name looks like "Dr. John Mushi" — drop the title, split first/last.
            name_parts = lect["name"].split()
            name_parts = name_parts[1:] if name_parts and name_parts[0].endswith(".") else name_parts
            first_name = name_parts[0] if name_parts else lect["name"]
            last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else "Lecturer"
            user, was_created = _get_or_skip_user(
                email,
                username=slug,
                first_name=first_name, last_name=last_name,
                phone=f"+256700800{phone_counter}",
                university_id=UNI_ID, department_id=dept_id,
                role_id=lecturer_role.id, is_active=True, is_approved=True,
                is_verified=True, must_change_password=True,
            )
            phone_counter += 1
            if was_created:
                user.set_password("Lecturer@2026")
                db.session.commit()
                result = _timetable_patch(f"/api/v1/lecturers/{lect['id']}", {"user_id": user.id})
                if result.get("success"):
                    wired += 1
                    print(f"  Wired {lect['name']} ({dept.get('code')}) -> {email}")

        print(f"\n=== Done. {wired} lecturer account(s) created and wired to Lecturer.user_id. ===\n")
        print("Standard KIU logins:")
        for role_name, _, _, email_pfx, _, pwd in ACCOUNTS:
            print(f"  {role_name:<18} {email_pfx}@{UNI_CODE}.shedulex.ac  /  {pwd}")
        print("\nEach seeded lecturer's login: <slugified-name>@kiu.shedulex.ac / Lecturer@2026")
        print("(must_change_password is set, so they'll be prompted to change it on first login)")


if __name__ == "__main__":
    seed()
