"""
LangChain tools that the AI agent can call to inspect and modify timetables.
Each tool communicates with the timetable-engine service via HTTP.
"""
import os
import httpx
from langchain_core.tools import tool

TIMETABLE_URL = os.environ.get("TIMETABLE_SERVICE_URL", "http://timetable-engine:5002")
INTERNAL_SERVICE_KEY = os.environ.get("INTERNAL_SERVICE_KEY", "dev-internal-service-key")


def _headers() -> dict:
    return {"X-Internal-Service-Key": INTERNAL_SERVICE_KEY}


def _get(path: str) -> dict:
    with httpx.Client(timeout=15) as client:
        resp = client.get(f"{TIMETABLE_URL}{path}", headers=_headers())
        resp.raise_for_status()
        return resp.json()


def _post(path: str, payload: dict) -> dict:
    with httpx.Client(timeout=15) as client:
        resp = client.post(f"{TIMETABLE_URL}{path}", json=payload, headers=_headers())
        resp.raise_for_status()
        return resp.json()


def _patch(path: str, payload: dict) -> dict:
    with httpx.Client(timeout=15) as client:
        resp = client.patch(f"{TIMETABLE_URL}{path}", json=payload, headers=_headers())
        resp.raise_for_status()
        return resp.json()


@tool
def get_timetable_entries(timetable_id: str) -> str:
    """Fetch all entries in a given timetable. Returns JSON of entries."""
    try:
        data = _get(f"/api/v1/timetable/{timetable_id}")
        return str(data.get("data", {}).get("entries", []))
    except Exception as e:
        return f"Error fetching timetable: {e}"


@tool
def detect_timetable_conflicts(timetable_id: str) -> str:
    """Detect all conflicts in a timetable (room clashes, lecturer double-bookings)."""
    try:
        data = _get(f"/api/v1/timetable/{timetable_id}/conflicts")
        return str(data.get("data", []))
    except Exception as e:
        return f"Error detecting conflicts: {e}"


@tool
def get_available_rooms(min_capacity: int = 0, requires_lab: bool = False) -> str:
    """Find available rooms filtered by capacity and type."""
    try:
        data = _get("/api/v1/rooms")
        rooms = data.get("data", [])
        filtered = [
            r for r in rooms
            if r.get("is_available", True)
            and r.get("capacity", 0) >= min_capacity
            and (not requires_lab or r.get("room_type") == "lab")
        ]
        return str(filtered)
    except Exception as e:
        return f"Error fetching rooms: {e}"


@tool
def get_lecturer_free_slots(lecturer_id: str, timetable_id: str) -> str:
    """Find free time slots for a specific lecturer in a timetable."""
    try:
        entries_data = _get(f"/api/v1/timetable/{timetable_id}")
        entries = entries_data.get("data", {}).get("entries", [])
        busy_slots = {
            e["time_slot"]["id"]
            for e in entries
            if e.get("lecturer", {}).get("id") == lecturer_id
        }
        slots_data = _get("/api/v1/time-slots")
        free = [s for s in slots_data.get("data", []) if s["id"] not in busy_slots]
        return str(free)
    except Exception as e:
        return f"Error finding free slots: {e}"


@tool
def swap_timetable_entries(entry1_id: str, entry2_id: str) -> str:
    """Swap the time slots of two timetable entries (drag-and-drop move)."""
    try:
        result = _post("/api/v1/timetable/entries/swap", {
            "entry1_id": entry1_id,
            "entry2_id": entry2_id,
        })
        return f"Swap successful: {result}"
    except Exception as e:
        return f"Swap failed: {e}"


@tool
def move_timetable_entry(entry_id: str, time_slot_id: str) -> str:
    """Move one timetable entry to a different time slot (no swap). Use when the target slot is free for that lecturer and room."""
    try:
        result = _patch(f"/api/v1/timetable/entries/{entry_id}", {"time_slot_id": time_slot_id})
        return f"Move successful: {result}"
    except Exception as e:
        return f"Move failed: {e}"


@tool
def suggest_best_venue(student_count: int, requires_lab: bool = False) -> str:
    """Suggest the best available venue for a class given student count and requirements."""
    try:
        data = _get("/api/v1/rooms")
        rooms = data.get("data", [])
        suitable = sorted(
            [r for r in rooms
             if r.get("is_available", True)
             and r.get("capacity", 0) >= student_count
             and (not requires_lab or r.get("room_type") == "lab")],
            key=lambda r: r["capacity"]
        )
        if suitable:
            best = suitable[0]
            return f"Best venue: {best['name']} (capacity={best['capacity']}, type={best['room_type']})"
        return "No suitable venue found."
    except Exception as e:
        return f"Error suggesting venue: {e}"


ALL_TOOLS = [
    get_timetable_entries,
    detect_timetable_conflicts,
    get_available_rooms,
    get_lecturer_free_slots,
    swap_timetable_entries,
    move_timetable_entry,
    suggest_best_venue,
]
