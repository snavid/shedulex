from app.models.domain import Timetable, TimetableEntry


def slot_payload(entry: TimetableEntry, slot=None) -> dict:
    slot = slot or entry.time_slot
    room = entry.room
    room_label = None
    if room:
        room_label = room.name or room.code
    return {
        "day": slot.day if slot else None,
        "start_time": slot.start_time if slot else None,
        "end_time": slot.end_time if slot else None,
        "room": room_label,
    }


def change_from_entry(entry: TimetableEntry, old_slot: dict | None = None, **extra) -> dict:
    course = entry.course
    lect = entry.lecturer
    payload = {
        "entry_id": entry.id,
        "course_code": course.code if course else None,
        "course_name": course.name if course else None,
        "lecturer_id": entry.lecturer_id,
        "lecturer_name": lect.name if lect else None,
        "lecturer_email": lect.email if lect else None,
        "lecturer_phone": lect.phone if lect else None,
        "lecturer_user_id": lect.user_id if lect else None,
        "student_group_id": entry.student_group_id,
        "program_id": course.program_id if course else None,
        "old_slot": old_slot,
        "new_slot": slot_payload(entry),
    }
    payload.update(extra)
    return payload


def base_event(timetable: Timetable, event_type: str, triggered_by: str | None = None, changes: list | None = None) -> dict:
    return {
        "event_type": event_type,
        "timetable_id": timetable.id,
        "department_id": timetable.department_id,
        "program_id": timetable.program_id,
        "timetable_name": timetable.name,
        "semester": timetable.semester,
        "academic_year": timetable.academic_year,
        "triggered_by": triggered_by or "system",
        "changes": changes or [],
    }
