from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from app.services import timetable_service
from app.security import service_or_jwt_required, is_internal_request
from app.utils.responses import fail, json_body, ok, require_fields

timetable_bp = Blueprint("timetable", __name__, url_prefix="/api/v1/timetable")


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
            config_overrides=body.get("ga_config"),
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
    sem = request.args.get("semester", type=int)
    status = request.args.get("status")
    timetables = timetable_service.list_timetables(dept, sem, status)
    return ok(data=[t.to_dict() for t in timetables])


@timetable_bp.get("/<timetable_id>")
@service_or_jwt_required()
def get_timetable(timetable_id):
    tt = timetable_service.get_timetable_by_id(timetable_id)
    if not tt:
        return fail("Timetable not found.", status=404)
    return ok(data=tt.to_dict(include_entries=True))


@timetable_bp.get("/<timetable_id>/conflicts")
@service_or_jwt_required()
def get_conflicts(timetable_id):
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
        e1, e2 = timetable_service.swap_entries(e1_id, e2_id)
    except ValueError as ex:
        return fail(str(ex), status=400)

    return ok(data={"entry1": e1.to_dict(), "entry2": e2.to_dict()})


@timetable_bp.get("/entries")
@service_or_jwt_required()
def list_entries():
    timetable_id = request.args.get("timetable_id")
    day = request.args.get("day")
    entries = timetable_service.list_entries(timetable_id=timetable_id, day=day)
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
