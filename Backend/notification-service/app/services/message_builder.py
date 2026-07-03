import os
from flask import current_app


SMS_MAX_LEN = 480


def _frontend_url() -> str:
    return current_app.config.get(
        "FRONTEND_URL", os.environ.get("FRONTEND_URL", "http://localhost:5173")
    )


def _timetable_link(timetable_id: str) -> str:
    return f"{_frontend_url()}/timetable/{timetable_id}"


def _truncate(text: str, limit: int = SMS_MAX_LEN) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _slot_label(slot: dict | None) -> str:
    if not slot:
        return "TBD"
    day = slot.get("day", "")
    start = slot.get("start_time", "")
    room = slot.get("room") if isinstance(slot.get("room"), str) else (slot.get("room_name") or "")
    label = f"{day} {start}".strip()
    if room:
        label += f" ({room})"
    return label


def _entry_summary(entry: dict) -> str:
    course = entry.get("course") or {}
    code = course.get("code") or course.get("name") or "Class"
    slot = entry.get("time_slot") or {}
    day = (slot.get("day") or "")[:3]
    start = slot.get("start_time") or ""
    room = (entry.get("room") or {}).get("name") or (entry.get("room") or {}).get("code") or ""
    parts = [f"{day} {code} {start}".strip()]
    if room:
        parts.append(room)
    return " ".join(parts)


def _change_summary(change: dict) -> str:
    code = change.get("course_code") or change.get("course_name") or "Class"
    if change.get("old_lecturer_id") and change.get("new_lecturer_id"):
        return f"{code} lecturer changed"
    if change.get("snapshot_id"):
        return "timetable restored from snapshot"
    old_slot = change.get("old_slot") or {}
    new_slot = change.get("new_slot") or {}
    old_label = f"{old_slot.get('day', '')[:3]} {old_slot.get('start_time', '')}".strip()
    new_label = f"{new_slot.get('day', '')[:3]} {new_slot.get('start_time', '')}".strip()
    room = new_slot.get("room") or ""
    msg = f"{code} {old_label}->{new_label}"
    if room:
        msg += f" ({room})"
    return msg


def build_student_message(
    *,
    timetable_id: str,
    semester: int,
    entries: list[dict],
    changes: list[dict],
    program_id: str | None,
    student_group_id: str | None,
    is_generation: bool,
) -> tuple[str, str]:
    link = _timetable_link(timetable_id)
    if is_generation:
        filtered = entries
        if program_id:
            filtered = [
                e for e in entries
                if (e.get("course") or {}).get("program_id") == program_id
            ]
        if student_group_id:
            filtered = [
                e for e in filtered
                if (e.get("student_group") or {}).get("id") == student_group_id
            ]
        summaries = [_entry_summary(e) for e in filtered[:4]]
        extra = len(filtered) - len(summaries)
        body = f"SheduleX: Your Sem {semester} timetable is ready. {', '.join(summaries)}"
        if extra > 0:
            body += f" (+{extra} more)"
        body += f". View: {link}"
        return f"Timetable Ready — Sem {semester}", _truncate(body)

    relevant = changes
    if student_group_id:
        relevant = [c for c in changes if c.get("student_group_id") == student_group_id]
    elif program_id:
        relevant = [c for c in changes if c.get("program_id") == program_id]
    if not relevant:
        return "", ""
    summaries = [_change_summary(c) for c in relevant[:3]]
    extra = len(relevant) - len(summaries)
    body = f"SheduleX Update: {', '.join(summaries)}"
    if extra > 0:
        body += f" (+{extra} more)"
    body += f". View: {link}"
    return "Timetable Update", _truncate(body)


def build_lecturer_message(
    *,
    timetable_id: str,
    lecturer_id: str,
    entries: list[dict],
    changes: list[dict],
    is_generation: bool,
) -> tuple[str, str]:
    link = _timetable_link(timetable_id)
    my_entries = [
        e for e in entries
        if (e.get("lecturer") or {}).get("id") == lecturer_id
    ]
    if is_generation:
        summaries = [_entry_summary(e) for e in my_entries[:5]]
        extra = len(my_entries) - len(summaries)
        body = f"SheduleX: Your teaching schedule is ready. {', '.join(summaries)}"
        if extra > 0:
            body += f" (+{extra} more)"
        body += f". View: {link}"
        return "Your Teaching Schedule", _truncate(body)

    my_changes = [
        c for c in changes
        if c.get("lecturer_id") == lecturer_id
        or c.get("old_lecturer_id") == lecturer_id
        or c.get("new_lecturer_id") == lecturer_id
    ]
    if not my_changes:
        return "", ""
    summaries = [_change_summary(c) for c in my_changes[:4]]
    extra = len(my_changes) - len(summaries)
    body = f"SheduleX: Your schedule updated. {', '.join(summaries)}"
    if extra > 0:
        body += f" (+{extra} more)"
    body += f". View: {link}"
    return "Schedule Updated", _truncate(body)


def build_hod_message(
    *,
    timetable_id: str,
    department_name: str,
    changes: list[dict],
    entry_count: int,
    is_generation: bool,
) -> tuple[str, str]:
    link = _timetable_link(timetable_id)
    if is_generation:
        body = (
            f"SheduleX: {department_name} timetable published with {entry_count} sessions. "
            f"View: {link}"
        )
        return f"{department_name} Timetable Published", _truncate(body)

    summaries = [_change_summary(c) for c in changes[:4]]
    extra = len(changes) - len(summaries)
    body = f"SheduleX: {department_name} timetable updated ({len(changes)} changes): {', '.join(summaries)}"
    if extra > 0:
        body += f" (+{extra} more)"
    body += f". View: {link}"
    return f"{department_name} Timetable Updated", _truncate(body)


def build_timetable_officer_message(
    *,
    timetable_id: str,
    timetable_name: str,
    department_name: str,
    changes: list[dict],
    triggered_by: str | None,
    entry_count: int,
    is_generation: bool,
) -> tuple[str, str]:
    link = _timetable_link(timetable_id)
    label = timetable_name or department_name
    actor = triggered_by if triggered_by and triggered_by != "system" else None

    if is_generation:
        body = (
            f"SheduleX: {label} timetable published ({entry_count} sessions)."
        )
        if actor:
            body += f" By {actor}."
        body += f" View: {link}"
        return f"Timetable Published — {label}", _truncate(body)

    summaries = [_change_summary(c) for c in changes[:4]]
    extra = len(changes) - len(summaries)
    body = f"SheduleX: {label} updated ({len(changes)} changes): {', '.join(summaries)}"
    if extra > 0:
        body += f" (+{extra} more)"
    if actor:
        body += f". By {actor}"
    body += f". View: {link}"
    return f"Timetable Updated — {label}", _truncate(body)
