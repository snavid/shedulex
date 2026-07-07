"""
LangChain tools for the Sora AI timetable assistant.

Every mutation tool immediately creates a version snapshot with a rich
description so the audit trail is complete (who did what and why).
"""
from __future__ import annotations

import logging
import os
import httpx
from langchain_core.tools import tool
from langgraph.types import interrupt

from app.services.timetable_snapshots import create_timetable_snapshot

logger = logging.getLogger(__name__)

TIMETABLE_URL = os.environ.get("TIMETABLE_SERVICE_URL", "http://timetable-engine:5002")
INTERNAL_KEY  = os.environ.get("INTERNAL_SERVICE_KEY", "dev-internal-service-key")


def _h():
    return {"X-Internal-Service-Key": INTERNAL_KEY}

def _get(path):
    with httpx.Client(timeout=20) as c:
        r = c.get(f"{TIMETABLE_URL}{path}", headers=_h())
        if r.status_code == 401:
            raise RuntimeError(f"401 Unauthorized — INTERNAL_SERVICE_KEY mismatch (key starts: {INTERNAL_KEY[:4]}…)")
        if r.status_code == 404:
            raise RuntimeError(f"404 Not Found: {TIMETABLE_URL}{path}")
        r.raise_for_status()
        return r.json()

def _post(path, payload):
    with httpx.Client(timeout=20) as c:
        r = c.post(f"{TIMETABLE_URL}{path}", json=payload, headers=_h()); r.raise_for_status(); return r.json()

def _patch(path, payload):
    with httpx.Client(timeout=20) as c:
        r = c.patch(f"{TIMETABLE_URL}{path}", json=payload, headers=_h()); r.raise_for_status(); return r.json()

def _delete(path):
    with httpx.Client(timeout=20) as c:
        r = c.delete(f"{TIMETABLE_URL}{path}", headers=_h()); r.raise_for_status(); return r.json()


# ── Read-only tools ───────────────────────────────────────────────────────────

@tool
def get_timetable_entries(timetable_id: str) -> str:
    """
    Fetch all scheduled entries for a timetable. Returns a compact list with
    entry_id, course code/name, year, program, room, lecturer, student_group,
    day, start_time, end_time, time_slot_id, and is_locked.
    ALWAYS call this first to get real IDs before any mutation.
    """
    try:
        data = _get(f"/api/v1/timetable/{timetable_id}")
        entries = (data.get("data") or {}).get("entries", [])
        summary = []
        for e in entries:
            course   = e.get("course")   or {}
            room     = e.get("room")     or {}
            lec      = e.get("lecturer") or {}
            group    = e.get("student_group") or {}
            ts       = e.get("time_slot") or {}
            program  = course.get("program") or {}
            summary.append({
                "entry_id":     e.get("id"),
                "course":       f"{course.get('code')} – {course.get('name')}",
                "year":         course.get("year_of_study"),
                "program":      program.get("code"),
                "room":         room.get("code"),
                "room_id":      room.get("id"),
                "lecturer":     lec.get("name"),
                "lecturer_id":  lec.get("id"),
                "group":        group.get("code"),
                "day":          ts.get("day"),
                "start_time":   ts.get("start_time"),
                "end_time":     ts.get("end_time"),
                "time_slot_id": e.get("time_slot", {}).get("id"),
                "is_locked":    e.get("is_locked", False),
            })
        return str(summary)
    except Exception as e:
        return f"Error fetching timetable: {e}"


@tool
def detect_timetable_conflicts(timetable_id: str) -> str:
    """
    Detect all hard conflicts: lecturer double-bookings, room double-bookings,
    student group clashes. Returns each conflict with the involved entries and slot.
    """
    try:
        data = _get(f"/api/v1/timetable/{timetable_id}/conflicts")
        return str(data.get("data", []))
    except Exception as e:
        return f"Error detecting conflicts: {e}"


@tool
def get_available_rooms(min_capacity: int = 0, requires_lab: bool = False) -> str:
    """
    List available rooms. Filter by minimum student capacity and lab requirement.
    Returns room id, name, code, capacity, and room_type.
    """
    try:
        data = _get("/api/v1/rooms")
        rooms = [r for r in (data.get("data") or [])
                 if r.get("is_available", True)
                 and r.get("capacity", 0) >= min_capacity
                 and (not requires_lab or r.get("room_type") == "lab")]
        return str(rooms)
    except Exception as e:
        return f"Error fetching rooms: {e}"


@tool
def get_lecturer_free_slots(lecturer_id: str, timetable_id: str) -> str:
    """
    Find all time slots where the lecturer has no session scheduled.
    Returns free slot objects (id, day, start_time, end_time).
    """
    try:
        entries_data = _get(f"/api/v1/timetable/{timetable_id}")
        entries = (entries_data.get("data") or {}).get("entries", [])
        busy = {(e.get("time_slot") or {}).get("id") for e in entries
                if (e.get("lecturer") or {}).get("id") == lecturer_id} - {None}
        slots_data = _get("/api/v1/time-slots")
        free = [s for s in (slots_data.get("data") or [])
                if s["id"] not in busy and not s.get("is_break")]
        return str(free)
    except Exception as e:
        return f"Error finding free slots: {e}"


@tool
def suggest_best_venue(student_count: int, requires_lab: bool = False) -> str:
    """
    Recommend the smallest room that fits the student count and type.
    Returns the best match with capacity, name, and room_type.
    """
    try:
        data = _get("/api/v1/rooms")
        suitable = sorted(
            [r for r in (data.get("data") or [])
             if r.get("is_available", True)
             and r.get("capacity", 0) >= student_count
             and (not requires_lab or r.get("room_type") == "lab")],
            key=lambda r: r["capacity"],
        )
        if suitable:
            b = suitable[0]
            return f"Best venue: {b['name']} ({b['code']}) — capacity {b['capacity']}, type: {b['room_type']}"
        return "No suitable venue found."
    except Exception as e:
        return f"Error suggesting venue: {e}"


# ── Mutation tools (each creates a snapshot) ─────────────────────────────────

@tool
def move_timetable_entry(
    timetable_id: str,
    entry_id: str,
    time_slot_id: str = "",
    room_id: str = "",
    reason: str = "",
) -> str:
    """
    Move one entry to a different time slot and/or room. Provide room_id whenever the
    conflict is about room capacity or room type — time_slot_id alone CANNOT change the
    assigned room, so a too-small room can only be fixed by also passing room_id. At
    least one of time_slot_id/room_id must be given. Always provide a reason for the
    audit trail.
    """
    if not time_slot_id and not room_id:
        return "Move failed: provide at least one of time_slot_id or room_id."
    try:
        entries_data = _get(f"/api/v1/timetable/{timetable_id}")
        entries = (entries_data.get("data") or {}).get("entries", [])
        entry = next((e for e in entries if e.get("id") == entry_id), {})

        payload = {}
        if time_slot_id:
            payload["time_slot_id"] = time_slot_id
        if room_id:
            payload["room_id"] = room_id
        _patch(f"/api/v1/timetable/entries/{entry_id}", payload)

        course   = entry.get("course")   or {}
        lec      = entry.get("lecturer") or {}
        old_ts   = entry.get("time_slot") or {}
        old_room = entry.get("room") or {}
        room_note = f" and room to {room_id}" if room_id else ""
        desc = (
            f"Sora AI moved {course.get('code', entry_id)} ({course.get('name', '')}) "
            f"from {old_ts.get('day','?')} {old_ts.get('start_time','?')} "
            f"(room {old_room.get('code','?')}) to slot {time_slot_id or old_ts.get('id')}{room_note}. "
            f"Lecturer: {lec.get('name','?')}. "
            f"Reason: {reason or 'AI schedule optimisation'}."
        )
        create_timetable_snapshot(timetable_id, desc, "Sora AI")
        return f"Move successful: {desc}"
    except Exception as e:
        return f"Move failed: {e}"


@tool
def swap_timetable_entries(
    timetable_id: str,
    entry1_id: str,
    entry2_id: str,
    reason: str = "",
) -> str:
    """
    Swap the time slots of TWO entries that are currently at DIFFERENT times.
    Do NOT use this to fix conflicts — conflicting entries are at the same time,
    so swapping them has no effect. Use move_timetable_entry to fix conflicts.
    Always provide a reason for the audit trail.
    """
    try:
        entries_data = _get(f"/api/v1/timetable/{timetable_id}")
        entries = (entries_data.get("data") or {}).get("entries", [])
        e1 = next((e for e in entries if e.get("id") == entry1_id), {})
        e2 = next((e for e in entries if e.get("id") == entry2_id), {})

        ts1 = e1.get("time_slot") or {}
        ts2 = e2.get("time_slot") or {}
        if ts1.get("id") and ts1.get("id") == ts2.get("id"):
            return (
                "Swap failed: both entries are in the same time slot — swapping them "
                "would have no visible effect. Use move_timetable_entry to move one of "
                "them to a different free slot instead."
            )

        _post("/api/v1/timetable/entries/swap", {"entry1_id": entry1_id, "entry2_id": entry2_id})

        c1, ts1 = e1.get("course") or {}, e1.get("time_slot") or {}
        c2, ts2 = e2.get("course") or {}, e2.get("time_slot") or {}
        desc = (
            f"Sora AI swapped {c1.get('code', entry1_id)} "
            f"({ts1.get('day','?')} {ts1.get('start_time','?')}) ↔ "
            f"{c2.get('code', entry2_id)} "
            f"({ts2.get('day','?')} {ts2.get('start_time','?')}). "
            f"Reason: {reason or 'AI schedule optimisation'}."
        )
        create_timetable_snapshot(timetable_id, desc, "Sora AI")
        return f"Swap successful: {desc}"
    except Exception as e:
        return f"Swap failed: {e}"


@tool
def get_available_lecturers(department_id: str = "") -> str:
    """
    List all active lecturers, optionally filtered by department.
    Returns lecturer id, name, email, specialization, and max_hours_per_week.
    Use this to find a replacement when a lecturer is sick or unavailable.
    """
    try:
        data = _get("/api/v1/lecturers")
        lecturers = data.get("data") or []
        if department_id:
            lecturers = [l for l in lecturers if (l.get("department") or {}).get("id") == department_id]
        summary = [
            {
                "id": l.get("id"),
                "name": l.get("name"),
                "email": l.get("email"),
                "specialization": l.get("specialization"),
                "max_hours_per_week": l.get("max_hours_per_week"),
                "department": (l.get("department") or {}).get("name"),
            }
            for l in lecturers
        ]
        return str(summary)
    except Exception as e:
        return f"Error fetching lecturers: {e}"


@tool
def substitute_lecturer(
    timetable_id: str,
    sick_lecturer_id: str,
    replacement_lecturer_id: str,
    reason: str = "",
) -> str:
    """
    Substitute a sick or absent lecturer with a replacement for ALL their sessions
    in this timetable. Call get_timetable_entries first to confirm the sick lecturer's
    entries. Call get_available_lecturers to find a qualified replacement.
    Always provide a reason (e.g. 'Lecturer sick — emergency substitution').
    """
    try:
        # Get names for the audit description
        entries_data = _get(f"/api/v1/timetable/{timetable_id}")
        entries = (entries_data.get("data") or {}).get("entries", [])
        sick_entries = [e for e in entries if (e.get("lecturer") or {}).get("id") == sick_lecturer_id]

        if not sick_entries:
            return f"No entries found for lecturer {sick_lecturer_id} in timetable {timetable_id}."

        sick_name = (sick_entries[0].get("lecturer") or {}).get("name", sick_lecturer_id)

        result = _post(f"/api/v1/timetable/{timetable_id}/substitute-lecturer", {
            "sick_lecturer_id": sick_lecturer_id,
            "replacement_lecturer_id": replacement_lecturer_id,
        })

        replacement = (result.get("data") or {}).get("replacement", {})
        replacement_name = replacement.get("name", replacement_lecturer_id)
        updated = (result.get("data") or {}).get("updated", 0)

        desc = (
            f"Sora AI substituted {sick_name} → {replacement_name} "
            f"for {updated} session(s) in timetable {timetable_id}. "
            f"Reason: {reason or 'Lecturer substitution'}."
        )
        create_timetable_snapshot(timetable_id, desc, "Sora AI")
        return f"Substitution successful: {desc}"
    except Exception as e:
        return f"Substitution failed: {e}"


@tool
def resolve_all_conflicts(timetable_id: str, reason: str = "") -> str:
    """
    Automatically re-optimize ALL currently-conflicting sessions in ONE shot using the
    scheduling engine — including conflicts a single move/swap cannot fix (e.g. a room
    that is too small for the class). Use this INSTEAD OF repeated move_timetable_entry
    calls whenever the user asks to fix "all" conflicts, or whenever
    detect_timetable_conflicts returns more than one conflict.
    """
    try:
        result = _post(f"/api/v1/timetable/{timetable_id}/reschedule", {"reason": reason})
        data = result.get("data") or {}
        updated = data.get("updated") or []
        desc = (
            f"Sora AI auto-resolved {len(updated)} conflicting session(s) in timetable "
            f"{timetable_id}. Reason: {reason or 'AI conflict resolution'}."
        )
        create_timetable_snapshot(timetable_id, desc, "Sora AI")
        return f"Resolved successfully: {desc}"
    except Exception as e:
        return f"Conflict resolution failed: {e}"


@tool
def bulk_reschedule(
    timetable_id: str,
    program_id: str = "",
    student_group_id: str = "",
    department_id: str = "",
    before_time: str = "",
    after_time: str = "",
    reason: str = "",
) -> str:
    """
    Move MANY sessions at once to satisfy a criteria-based directive, e.g. "move all of
    BCS Year 3 to mornings before 12:00" or "move everything in the CS department after
    14:00". Provide program_id and/or student_group_id and/or department_id to select
    WHICH sessions move, and before_time/after_time ("HH:MM", 24h) to constrain WHEN they
    may land. Use this INSTEAD OF calling move_timetable_entry one-by-one for "all of X"
    requests — it re-optimizes everything together in one engine call.
    """
    try:
        payload = {"reason": reason}
        for key, val in (("program_id", program_id), ("student_group_id", student_group_id),
                         ("department_id", department_id), ("before_time", before_time),
                         ("after_time", after_time)):
            if val:
                payload[key] = val
        result = _post(f"/api/v1/timetable/{timetable_id}/reschedule", payload)
        data = result.get("data") or {}
        updated = data.get("updated") or []
        desc = (
            f"Sora AI bulk-rescheduled {len(updated)} session(s) in timetable {timetable_id} "
            f"(program={program_id or '-'}, group={student_group_id or '-'}, "
            f"dept={department_id or '-'}, before={before_time or '-'}, after={after_time or '-'}). "
            f"Reason: {reason or 'AI bulk reschedule'}."
        )
        create_timetable_snapshot(timetable_id, desc, "Sora AI")
        return f"Bulk reschedule successful: {desc}"
    except Exception as e:
        return f"Bulk reschedule failed: {e}"


# ── Human-in-the-loop ─────────────────────────────────────────────────────────

@tool
def ask_user(question: str) -> str:
    """
    Pause and ask the human user a question when their decision is needed.
    Use this whenever you encounter a conflict with no clear best resolution —
    for example, which session to prioritise, whether to force-place despite a clash,
    or which of several free slots to use.

    Format the question as:
      1. What is the conflict / situation?
      2. What are the options? (Label them A, B, C …)
      3. What does each option do?

    After the user responds, implement their chosen option automatically.
    """
    answer = interrupt({"type": "user_input", "question": question})
    return f"User decided: {answer}"


ALL_TOOLS = [
    get_timetable_entries,
    detect_timetable_conflicts,
    get_available_rooms,
    get_lecturer_free_slots,
    suggest_best_venue,
    move_timetable_entry,
    swap_timetable_entries,
    resolve_all_conflicts,
    bulk_reschedule,
    get_available_lecturers,
    substitute_lecturer,
    ask_user,
]
