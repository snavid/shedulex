from flask import Blueprint, request
from flask_jwt_extended import get_jwt, get_jwt_identity
from app.services import timetable_service
from app.security import service_or_jwt_required, is_internal_request, get_jwt_university_id
from app.utils.responses import fail, json_body, ok, require_fields

timetable_bp = Blueprint("timetable", __name__, url_prefix="/api/v1/timetable")


def _check_timetable_access(tt):
    """Return a 404 fail response if the caller's university doesn't own the timetable, else None."""
    if is_internal_request():
        return None
    uni_id = get_jwt_university_id()
    if uni_id:
        dept = getattr(tt, "department", None)
        if not dept or dept.university_id != uni_id:
            return fail("Timetable not found.", status=404)
    return None


@timetable_bp.post("/generate")
@service_or_jwt_required("admin", "timetable_officer")
def generate():
    body = json_body()
    required = ["department_id", "semester", "academic_year", "name"]
    is_valid, missing = require_fields(body, required)
    if not is_valid:
        return fail(f"'{missing}' is required.", status=422)

    try:
        timetable = timetable_service.generate_timetable(
            department_id=body["department_id"],
            semester=int(body["semester"]),
            academic_year=body["academic_year"],
            name=body["name"],
            created_by=body.get("created_by") if is_internal_request() else get_jwt_identity(),
            program_id=body.get("program_id"),
            template_id=body.get("template_id"),
            calendar_semester_id=body.get("calendar_semester_id"),
            academic_year_id=body.get("academic_year_id"),
            config_overrides=body.get("ga_config"),
            student_group_ids=body.get("student_group_ids") or None,
        )
    except (ValueError, RuntimeError) as e:
        return fail(str(e), status=400)

    return ok(
        message="Timetable generated successfully.",
        data=timetable.to_dict(include_entries=True),
        status=201,
    )


@timetable_bp.get("/")
@service_or_jwt_required()
def list_timetables():
    dept = request.args.get("department_id")
    prog = request.args.get("program_id")
    sem = request.args.get("semester", type=int)
    status = request.args.get("status")
    academic_year_id = request.args.get("academic_year_id")
    # Internal services may pass ?university_id= to scope results; JWT requests are always scoped by claims.
    university_id = request.args.get("university_id") if is_internal_request() else get_jwt_university_id()
    timetables = timetable_service.list_timetables(dept, sem, status, prog, academic_year_id, university_id)
    return ok(data=[t.to_dict() for t in timetables])


@timetable_bp.get("/<timetable_id>")
@service_or_jwt_required()
def get_timetable(timetable_id):
    tt = timetable_service.get_timetable_by_id(timetable_id)
    if not tt:
        return fail("Timetable not found.", status=404)
    err = _check_timetable_access(tt)
    if err:
        return err
    return ok(data=tt.to_dict(include_entries=True))


@timetable_bp.get("/<timetable_id>/conflicts")
@service_or_jwt_required()
def get_conflicts(timetable_id):
    tt = timetable_service.get_timetable_by_id(timetable_id)
    if not tt:
        return fail("Timetable not found.", status=404)
    err = _check_timetable_access(tt)
    if err:
        return err
    conflicts = timetable_service.detect_conflicts(timetable_id)
    return ok(data=conflicts, extra={"total": len(conflicts)})


@timetable_bp.post("/entries/swap")
@service_or_jwt_required("admin", "timetable_officer")
def swap_entries():
    body = json_body()
    e1_id = body.get("entry1_id")
    e2_id = body.get("entry2_id")
    if not e1_id or not e2_id:
        return fail("entry1_id and entry2_id required.", status=422)

    try:
        actor = body.get("triggered_by") if is_internal_request() else get_jwt_identity()
        e1, e2 = timetable_service.swap_entries(e1_id, e2_id, triggered_by=actor)
    except ValueError as ex:
        return fail(str(ex), status=400)

    return ok(data={"entry1": e1.to_dict(), "entry2": e2.to_dict()})


@timetable_bp.get("/entries/<entry_id>")
@service_or_jwt_required()
def get_entry(entry_id):
    from app.models.domain import TimetableEntry

    entry = TimetableEntry.query.get(entry_id)
    if not entry:
        return fail("Timetable entry not found.", status=404)

    denied = _check_timetable_access(entry.timetable)
    if denied:
        return denied

    data = entry.to_dict()
    data["timetable_id"] = entry.timetable_id
    data["student_group_id"] = entry.student_group_id
    return ok(data=data)


@timetable_bp.patch("/entries/<entry_id>")
@service_or_jwt_required("admin", "timetable_officer")
def move_entry(entry_id):
    """Assign a single entry to a new time slot and/or room (no swap). Internal services may call via X-Internal-Service-Key."""
    body = json_body()
    slot_id = body.get("time_slot_id")
    room_id = body.get("room_id")
    if not slot_id and not room_id:
        return fail("time_slot_id or room_id is required.", status=422)

    try:
        actor = body.get("triggered_by") if is_internal_request() else get_jwt_identity()
        entry = timetable_service.move_entry_to_slot(entry_id, slot_id, room_id=room_id, triggered_by=actor)
    except ValueError as ex:
        return fail(str(ex), status=400)

    return ok(data=entry.to_dict())


@timetable_bp.post("/<timetable_id>/reschedule")
@service_or_jwt_required("admin", "timetable_officer")
def reschedule(timetable_id):
    """
    Scoped GA re-optimization of a subset of this timetable's entries — either an
    explicit list of target_entry_ids, a program/student_group/department filter,
    or (if none given) every entry currently implicated by a conflict. Leaves every
    other entry in the timetable untouched. Internal services may call via
    X-Internal-Service-Key.
    """
    body = json_body()
    try:
        actor = body.get("triggered_by") if is_internal_request() else get_jwt_identity()
        result = timetable_service.reschedule_subset(
            timetable_id,
            target_entry_ids=body.get("target_entry_ids"),
            program_id=body.get("program_id"),
            student_group_id=body.get("student_group_id"),
            department_id=body.get("department_id"),
            before_time=body.get("before_time"),
            after_time=body.get("after_time"),
            config_overrides=body.get("ga_config"),
            triggered_by=actor,
        )
    except (ValueError, RuntimeError) as e:
        return fail(str(e), status=400)

    return ok(
        data=result,
        message=f"Rescheduled {len(result.get('updated', []))} session(s).",
    )


@timetable_bp.get("/entries")
@service_or_jwt_required()
def list_entries():
    timetable_id = request.args.get("timetable_id")
    day = request.args.get("day")
    lecturer_id = request.args.get("lecturer_id")
    department_id = request.args.get("department_id")

    if not is_internal_request() and get_jwt().get("role") == "lecturer":
        from app.models.domain import Lecturer
        me = Lecturer.query.filter_by(user_id=get_jwt_identity(), is_active=True).first()
        lecturer_id = me.id if me else "__none__"  # force empty result if no linked Lecturer row

    entries = timetable_service.list_entries(
        timetable_id=timetable_id, day=day, lecturer_id=lecturer_id, department_id=department_id,
    )
    return ok(data=[e.to_dict() for e in entries])


@timetable_bp.post("/<timetable_id>/predict-conflicts")
@service_or_jwt_required("admin", "timetable_officer", "hod")
def predict_conflicts(timetable_id):
    predictions = timetable_service.predict_conflicts(timetable_id)
    return ok(data=predictions, extra={"total": len(predictions)})


@timetable_bp.post("/<timetable_id>/versions")
@service_or_jwt_required("admin", "timetable_officer")
def create_version_snapshot(timetable_id):
    body = json_body()
    notes = body.get("notes", "")
    actor = body.get("created_by") if is_internal_request() else get_jwt_identity()
    try:
        snapshot = timetable_service.create_snapshot(timetable_id, actor, notes)
    except ValueError as ex:
        return fail(str(ex), status=404)

    return ok(data=snapshot.to_dict(), status=201)


@timetable_bp.get("/<timetable_id>/versions")
@service_or_jwt_required()
def list_versions(timetable_id):
    tt = timetable_service.get_timetable_by_id(timetable_id)
    if not tt:
        return fail("Timetable not found.", status=404)
    err = _check_timetable_access(tt)
    if err:
        return err
    versions = timetable_service.list_snapshots(timetable_id)
    return ok(data=[v.to_dict() for v in versions])


@timetable_bp.post("/versions/<snapshot_id>/restore")
@service_or_jwt_required("admin", "timetable_officer")
def restore_version(snapshot_id):
    try:
        restored = timetable_service.restore_snapshot(snapshot_id)
    except ValueError as ex:
        return fail(str(ex), status=404)
    return ok(data=restored.to_dict(include_entries=True))


@timetable_bp.get("/<timetable_id>/violations")
@service_or_jwt_required()
def get_violations(timetable_id):
    """Recompute and return constraint violations for the current timetable state."""
    tt = timetable_service.get_timetable_by_id(timetable_id)
    if not tt:
        return fail("Timetable not found.", status=404)
    err = _check_timetable_access(tt)
    if err:
        return err
    report = timetable_service.get_violation_report(timetable_id)
    return ok(data=report, extra={"total": len(report)})


@timetable_bp.patch("/<timetable_id>/entries/<entry_id>/lock")
@service_or_jwt_required("admin", "timetable_officer")
def toggle_lock(timetable_id, entry_id):
    """Lock or unlock a single timetable entry."""
    from app.models.domain import TimetableEntry
    entry = TimetableEntry.query.filter_by(id=entry_id, timetable_id=timetable_id).first_or_404()
    entry.is_locked = not entry.is_locked
    from app.extensions import db
    db.session.commit()
    return ok(data=entry.to_dict())


@timetable_bp.patch("/<timetable_id>")
@service_or_jwt_required("admin", "timetable_officer")
def update_timetable(timetable_id):
    body = json_body()
    tt = timetable_service.get_timetable_by_id(timetable_id)
    if not tt:
        return fail("Timetable not found.", status=404)
    err = _check_timetable_access(tt)
    if err:
        return err
    if "calendar_semester_id" not in body and "name" not in body:
        return fail("No updatable fields provided.", status=422)
    updates = {}
    if "calendar_semester_id" in body:
        updates["calendar_semester_id"] = body["calendar_semester_id"]
    if "name" in body:
        updates["name"] = body["name"]
    try:
        updated = timetable_service.update_timetable_metadata(timetable_id, **updates)
    except ValueError as ex:
        return fail(str(ex), status=404)
    return ok(data=updated.to_dict(), message="Timetable updated.")


@timetable_bp.patch("/<timetable_id>/archive")
@service_or_jwt_required("admin", "timetable_officer")
def archive_timetable(timetable_id):
    from app.models.domain import Timetable
    from app.extensions import db
    tt = Timetable.query.get_or_404(timetable_id)
    tt.status = "archived"
    db.session.commit()
    return ok(data=tt.to_dict(), message="Timetable archived.")


@timetable_bp.delete("/<timetable_id>")
@service_or_jwt_required("admin", "timetable_officer")
def delete_timetable(timetable_id):
    """Permanently delete a timetable and all its entries."""
    tt = timetable_service.get_timetable_by_id(timetable_id)
    if not tt:
        return fail("Timetable not found.", status=404)
    err = _check_timetable_access(tt)
    if err:
        return err
    try:
        timetable_service.delete_timetable(timetable_id)
    except ValueError as e:
        return fail(str(e), status=404)
    return ok(message="Timetable deleted.")
