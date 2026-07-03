import os

import httpx
from flask import current_app


def _auth_base_url() -> str:
    return current_app.config.get(
        "AUTH_SERVICE_URL",
        os.environ.get("AUTH_SERVICE_URL", "http://auth-service:5001"),
    )


def _headers() -> dict:
    return {
        "X-Internal-Service-Key": current_app.config.get(
            "INTERNAL_SERVICE_KEY", os.environ.get("INTERNAL_SERVICE_KEY", "")
        ),
    }


def fetch_recipients(**filters) -> list[dict]:
    """Fetch all matching recipients from auth-service, paginating internally."""
    results: list[dict] = []
    page = 1
    per_page = 500
    while True:
        params = {**filters, "page": page, "per_page": per_page}
        params = {k: v for k, v in params.items() if v is not None}
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(
                    f"{_auth_base_url()}/api/v1/users/internal/recipients",
                    params=params,
                    headers=_headers(),
                )
                if resp.status_code != 200:
                    current_app.logger.error("Auth recipients API failed: %s", resp.text)
                    break
                body = resp.json()
                results.extend(body.get("data") or [])
                meta = body.get("meta") or {}
                if page >= meta.get("pages", 1):
                    break
                page += 1
        except Exception as exc:
            current_app.logger.error("Auth recipients fetch error: %s", exc)
            break
    return results


def fetch_user_by_id(user_id: str) -> dict | None:
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"{_auth_base_url()}/api/v1/users/internal/{user_id}",
                headers=_headers(),
            )
            if resp.status_code != 200:
                return None
            return resp.json().get("data")
    except Exception:
        return None


def fetch_user_by_email(email: str) -> dict | None:
    if not email:
        return None
    users = fetch_recipients(email=email)
    return users[0] if users else None


def _enrich_lecturer_contact(contact: dict) -> dict:
    phone = contact.get("phone")
    email = contact.get("email")
    user_id = contact.get("id")

    auth_user_id = contact.get("lecturer_user_id")
    if auth_user_id:
        user = fetch_user_by_id(auth_user_id)
        if user:
            phone = phone or user.get("phone")
            email = email or user.get("email")
            user_id = user.get("id")

    if not phone and email:
        user = fetch_user_by_email(email)
        if user:
            phone = user.get("phone")
            email = email or user.get("email")
            user_id = user.get("id")

    contact["phone"] = phone
    contact["email"] = email
    contact["id"] = user_id or contact.get("lecturer_id")
    contact.pop("lecturer_user_id", None)
    return contact


def resolve_lecturer_contacts(entries: list[dict], lecturer_ids: set[str]) -> dict[str, dict]:
    """Map lecturer_id -> contact info using timetable entry data and auth fallback."""
    contacts: dict[str, dict] = {}
    for entry in entries:
        lecturer = entry.get("lecturer") or {}
        lec_id = lecturer.get("id")
        if not lec_id or lec_id not in lecturer_ids:
            continue
        if lec_id in contacts:
            continue
        contact = {
            "id": lecturer.get("user_id") or lec_id,
            "lecturer_id": lec_id,
            "phone": lecturer.get("phone"),
            "email": lecturer.get("email"),
            "name": lecturer.get("name") or "Lecturer",
            "role": "lecturer",
        }
        contacts[lec_id] = _enrich_lecturer_contact(contact)
    return contacts


def resolve_lecturer_contacts_from_changes(
    changes: list[dict],
    entries: list[dict],
    lecturer_ids: set[str],
) -> dict[str, dict]:
    """Build lecturer contacts from change payloads, with entry/auth fallbacks."""
    contacts: dict[str, dict] = {}

    for change in changes:
        lec_id = change.get("lecturer_id")
        if not lec_id or lec_id not in lecturer_ids or lec_id in contacts:
            continue
        contact = {
            "id": change.get("lecturer_user_id") or lec_id,
            "lecturer_id": lec_id,
            "phone": change.get("lecturer_phone"),
            "email": change.get("lecturer_email"),
            "name": change.get("lecturer_name") or "Lecturer",
            "role": "lecturer",
            "lecturer_user_id": change.get("lecturer_user_id"),
        }
        contacts[lec_id] = _enrich_lecturer_contact(contact)

    for lec_id, contact in resolve_lecturer_contacts(entries, lecturer_ids).items():
        if lec_id not in contacts:
            contacts[lec_id] = contact
        else:
            existing = contacts[lec_id]
            for field in ("phone", "email", "name", "id"):
                if not existing.get(field) and contact.get(field):
                    existing[field] = contact[field]

    return contacts


def resolve_hod_recipients(
    department_id: str | None,
    university_id: str | None,
) -> list[dict]:
    """Resolve HOD accounts for a timetable department."""
    hods: list[dict] = []
    seen: set[str] = set()

    if department_id:
        filters: dict = {"role": "hod", "department_id": department_id}
        if university_id:
            filters["university_id"] = university_id
        for hod in fetch_recipients(**filters):
            if hod["id"] not in seen:
                seen.add(hod["id"])
                hods.append(hod)

    if not hods and university_id:
        for hod in fetch_recipients(role="hod", university_id=university_id):
            if hod.get("department_id"):
                continue
            if hod["id"] not in seen:
                seen.add(hod["id"])
                hods.append(hod)

    return hods


def resolve_timetable_officer_recipients(
    university_id: str | None,
    department_id: str | None = None,
) -> list[dict]:
    """Resolve timetable officers scoped to university (and optionally department)."""
    if not university_id:
        return []

    officers: list[dict] = []
    for officer in fetch_recipients(role="timetable_officer", university_id=university_id):
        officer_dept = officer.get("department_id")
        if officer_dept and department_id and officer_dept != department_id:
            continue
        officers.append(officer)
    return officers


def resolve_all_recipients(
    *,
    department_id: str,
    university_id: str | None,
    affected_program_ids: set[str],
    affected_group_ids: set[str],
    affected_lecturer_ids: set[str],
    entries: list[dict],
    changes: list[dict] | None = None,
    is_generation: bool,
) -> list[dict]:
    """Build deduplicated recipient list with role-specific targeting."""
    recipients: dict[str, dict] = {}
    changes = changes or []

    def add_recipient(contact: dict, priority: int):
        phone = contact.get("phone")
        email = contact.get("email")
        key = phone or email or contact.get("id")
        if not key:
            return
        existing = recipients.get(key)
        if existing and existing.get("_priority", 0) >= priority:
            return
        recipients[key] = {**contact, "_priority": priority}

    for lec_id, contact in resolve_lecturer_contacts_from_changes(
        changes, entries, affected_lecturer_ids
    ).items():
        add_recipient(contact, priority=3)

    for hod in resolve_hod_recipients(department_id, university_id):
        add_recipient({**hod, "role": "hod"}, priority=2)

    for officer in resolve_timetable_officer_recipients(university_id, department_id):
        add_recipient({**officer, "role": "timetable_officer"}, priority=2)

    if is_generation:
        program_ids = affected_program_ids or {
            (e.get("course") or {}).get("program_id")
            for e in entries
            if (e.get("course") or {}).get("program_id")
        }
        for program_id in program_ids:
            if not program_id:
                continue
            student_filters = {"role": "student", "program_id": program_id}
            if university_id:
                student_filters["university_id"] = university_id
            for student in fetch_recipients(**student_filters):
                add_recipient({**student, "role": "student"}, priority=1)
    else:
        for group_id in affected_group_ids:
            student_filters = {"role": "student", "student_group_id": group_id}
            if university_id:
                student_filters["university_id"] = university_id
            for student in fetch_recipients(**student_filters):
                add_recipient({**student, "role": "student"}, priority=1)
        for program_id in affected_program_ids:
            if affected_group_ids:
                continue
            student_filters = {"role": "student", "program_id": program_id}
            if university_id:
                student_filters["university_id"] = university_id
            for student in fetch_recipients(**student_filters):
                add_recipient({**student, "role": "student"}, priority=1)

    result = []
    for contact in recipients.values():
        contact.pop("_priority", None)
        result.append(contact)
    return result


def resolve_broadcast_audience(
    *,
    audience: str,
    university_id: str | None = None,
    department_id: str | None = None,
    program_id: str | None = None,
) -> list[dict]:
    """Resolve recipients for manual broadcast by audience role."""
    recipients: dict[str, dict] = {}

    def add_user(user: dict):
        phone = user.get("phone")
        email = user.get("email")
        key = phone or email or user.get("id")
        if not key:
            return
        recipients[key] = user

    base_filters: dict = {}
    if university_id:
        base_filters["university_id"] = university_id
    if department_id:
        base_filters["department_id"] = department_id
    if program_id:
        base_filters["program_id"] = program_id

    roles = []
    if audience == "students":
        roles = ["student"]
    elif audience == "lecturers":
        roles = ["lecturer"]
    elif audience == "hod":
        roles = ["hod"]
    elif audience == "all":
        roles = ["student", "lecturer", "hod", "timetable_officer", "admin"]

    for role in roles:
        filters = {**base_filters, "role": role}
        for user in fetch_recipients(**filters):
            add_user(user)

    return list(recipients.values())


def resolve_calendar_event_recipients(event: dict) -> list[dict]:
    """Resolve SMS recipients scoped to a calendar academic event."""
    recipients: dict[str, dict] = {}
    university_id = event.get("university_id")
    department_id = event.get("department_id")
    program_id = event.get("program_id")
    student_group_id = event.get("student_group_id")

    def add_user(user: dict):
        key = user.get("phone") or user.get("email") or user.get("id")
        if key:
            recipients[key] = user

    base: dict = {}
    if university_id:
        base["university_id"] = university_id

    if student_group_id:
        for user in fetch_recipients(**base, role="student", student_group_id=student_group_id):
            add_user(user)
    elif program_id:
        for user in fetch_recipients(**base, role="student", program_id=program_id):
            add_user(user)
        for user in fetch_recipients(**base, role="lecturer", program_id=program_id):
            add_user(user)
    elif department_id:
        dept_base = {**base, "department_id": department_id}
        for role in ("student", "lecturer", "hod"):
            for user in fetch_recipients(**dept_base, role=role):
                add_user(user)
    elif university_id:
        for role in ("student", "lecturer", "hod"):
            for user in fetch_recipients(**base, role=role):
                add_user(user)

    return list(recipients.values())
