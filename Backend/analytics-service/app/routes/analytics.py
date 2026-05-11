"""
Analytics Service — computes scheduling metrics by querying the timetable engine.
Returns data ready for dashboard charts.
"""
import os
import httpx
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/v1/analytics")

TIMETABLE_URL = os.environ.get("TIMETABLE_SERVICE_URL", "http://timetable-engine:5002")
INTERNAL_SERVICE_KEY = os.environ.get("INTERNAL_SERVICE_KEY", "dev-internal-service-key")


def _get(path: str) -> dict:
    with httpx.Client(timeout=15) as client:
        resp = client.get(
            f"{TIMETABLE_URL}{path}",
            headers={"X-Internal-Service-Key": INTERNAL_SERVICE_KEY},
        )
        resp.raise_for_status()
        return resp.json()


@analytics_bp.get("/overview")
@jwt_required()
def overview():
    """High-level KPIs for the dashboard."""
    try:
        timetables = _get("/api/v1/timetable/")
        rooms = _get("/api/v1/rooms")
        lecturers = _get("/api/v1/lecturers")
        courses = _get("/api/v1/courses")

        active_timetables = [t for t in timetables.get("data", []) if t.get("status") == "active"]
        avg_fitness = sum(t.get("fitness_score", 0) for t in active_timetables) / max(len(active_timetables), 1)

        return jsonify({
            "success": True,
            "data": {
                "total_timetables": len(timetables.get("data", [])),
                "active_timetables": len(active_timetables),
                "total_rooms": len(rooms.get("data", [])),
                "total_lecturers": len(lecturers.get("data", [])),
                "total_courses": len(courses.get("data", [])),
                "average_fitness_score": round(avg_fitness, 4),
                "optimization_quality": "Excellent" if avg_fitness > 0.9 else "Good" if avg_fitness > 0.75 else "Fair",
            },
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@analytics_bp.get("/timetable/<timetable_id>/metrics")
@jwt_required()
def timetable_metrics(timetable_id):
    """Detailed metrics for a specific timetable."""
    try:
        data = _get(f"/api/v1/timetable/{timetable_id}")
        timetable = data.get("data", {})
        entries = timetable.get("entries", [])

        # Room utilization
        room_usage: dict = {}
        lecturer_hours: dict = {}
        day_distribution: dict = {d: 0 for d in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]}
        conflict_data = _get(f"/api/v1/timetable/{timetable_id}/conflicts").get("data", [])

        for entry in entries:
            room = entry.get("room", {})
            lecturer = entry.get("lecturer", {})
            slot = entry.get("time_slot", {})

            room_id = room.get("id", "unknown")
            room_usage[room_id] = room_usage.get(room_id, {"name": room.get("name", ""), "count": 0})
            room_usage[room_id]["count"] += 1

            lec_id = lecturer.get("id", "unknown")
            lecturer_hours[lec_id] = lecturer_hours.get(lec_id, {"name": lecturer.get("name", ""), "hours": 0})
            lecturer_hours[lec_id]["hours"] += 1

            day = slot.get("day", "")
            if day in day_distribution:
                day_distribution[day] += 1

        return jsonify({
            "success": True,
            "data": {
                "timetable_id": timetable_id,
                "fitness_score": timetable.get("fitness_score"),
                "total_entries": len(entries),
                "total_conflicts": len(conflict_data),
                "conflicts": conflict_data,
                "room_utilization": list(room_usage.values()),
                "lecturer_workload": list(lecturer_hours.values()),
                "day_distribution": day_distribution,
                "generations_run": timetable.get("generations_run"),
                "generation_time": timetable.get("generation_time_seconds"),
            },
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@analytics_bp.get("/rooms/utilization")
@jwt_required()
def room_utilization():
    """Room utilization across all active timetables."""
    try:
        rooms = _get("/api/v1/rooms").get("data", [])
        timetables = _get("/api/v1/timetable/?status=active").get("data", [])
        room_counts = {r["id"]: {"name": r["name"], "capacity": r["capacity"], "bookings": 0} for r in rooms}

        for tt in timetables:
            detail = _get(f"/api/v1/timetable/{tt['id']}")
            for entry in detail.get("data", {}).get("entries", []):
                room_id = entry.get("room", {}).get("id")
                if room_id in room_counts:
                    room_counts[room_id]["bookings"] += 1

        return jsonify({"success": True, "data": list(room_counts.values())}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@analytics_bp.get("/lecturers/workload")
@jwt_required()
def lecturer_workload():
    """Lecturer workload analysis across active timetables."""
    try:
        lecturers = _get("/api/v1/lecturers").get("data", [])
        lec_data = {l["id"]: {"name": l["name"], "email": l["email"], "hours": 0, "max": l.get("max_hours_per_week", 20)} for l in lecturers}
        timetables = _get("/api/v1/timetable/?status=active").get("data", [])

        for tt in timetables:
            detail = _get(f"/api/v1/timetable/{tt['id']}")
            for entry in detail.get("data", {}).get("entries", []):
                lec_id = entry.get("lecturer", {}).get("id")
                if lec_id in lec_data:
                    lec_data[lec_id]["hours"] += 1

        result = list(lec_data.values())
        for l in result:
            l["utilization_pct"] = round(l["hours"] / max(l["max"], 1) * 100, 1)

        return jsonify({"success": True, "data": result}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
