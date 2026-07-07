"""
Two-tier lecturer -> HOD -> admin request workflow.

Status flow:
  lecturer creates  -> pending_hod
  hod creates       -> pending_admin (a HOD has no one above them at the HOD stage)
  hod approves      -> pending_admin
  hod rejects       -> rejected   (never becomes visible to admin as "pending", but
                                    IS visible under a "rejected" filter for oversight)
  admin approves     -> approved
  admin rejects      -> rejected
"""
from datetime import datetime, timezone

from flask import Blueprint, request
from flask_jwt_extended import get_jwt, get_jwt_identity

from app.extensions import db
from app.models.domain import Department, Lecturer, LecturerRequest
from app.security import get_jwt_university_id, is_internal_request, service_or_jwt_required
from app.utils.responses import fail, json_body, ok

lecturer_requests_bp = Blueprint("lecturer_requests", __name__, url_prefix="/api/v1/lecturer-requests")

CATEGORIES = ("schedule_change", "substitution_leave", "room_issue", "other")


@lecturer_requests_bp.post("/")
@service_or_jwt_required("lecturer", "hod")
def create_request():
    claims = get_jwt()
    role = claims.get("role")
    uid = get_jwt_identity()
    body = json_body()

    category = body.get("category")
    message = (body.get("message") or "").strip()
    if category not in CATEGORIES:
        return fail(f"category must be one of {CATEGORIES}.", status=422)
    if not message:
        return fail("message is required.", status=422)

    lecturer_name = claims.get("email")
    if role == "hod":
        department_id = claims.get("department_id")
        if not department_id:
            return fail("Your account has no assigned department. Contact an administrator.", status=422)
        status = "pending_admin"
    else:
        lecturer = Lecturer.query.filter_by(user_id=uid, is_active=True).first()
        if not lecturer or not lecturer.department_id:
            return fail("No department found for your lecturer profile.", status=422)
        department_id = lecturer.department_id
        lecturer_name = lecturer.name or lecturer_name
        status = "pending_hod"

    req = LecturerRequest(
        lecturer_user_id=uid,
        lecturer_name=lecturer_name,
        department_id=department_id,
        category=category,
        message=message[:1000],
        status=status,
    )
    db.session.add(req)
    db.session.commit()
    return ok(data=req.to_dict(), status=201)


@lecturer_requests_bp.get("/")
@service_or_jwt_required("lecturer", "hod", "admin", "timetable_officer")
def list_requests():
    claims = get_jwt()
    role = claims.get("role")
    uid = get_jwt_identity()
    q = LecturerRequest.query

    if role == "lecturer":
        q = q.filter_by(lecturer_user_id=uid)
    elif role == "hod":
        if request.args.get("mine") == "true":
            q = q.filter_by(lecturer_user_id=uid)
        else:
            dept_id = claims.get("department_id")
            if not dept_id:
                return ok(data=[])
            q = q.filter_by(department_id=dept_id, status="pending_hod")
    else:  # admin / timetable_officer — never see pending_hod
        uni_id = get_jwt_university_id()
        if uni_id:
            q = q.join(Department, LecturerRequest.department_id == Department.id).filter(
                Department.university_id == uni_id
            )
        q = q.filter(LecturerRequest.status.in_(("pending_admin", "approved", "rejected")))
        status_filter = request.args.get("status")
        if status_filter in ("pending_admin", "approved", "rejected"):
            q = q.filter(LecturerRequest.status == status_filter)

    return ok(data=[r.to_dict() for r in q.order_by(LecturerRequest.created_at.desc()).all()])


@lecturer_requests_bp.patch("/<req_id>/hod-decision")
@service_or_jwt_required("hod")
def hod_decide(req_id):
    dept_id = get_jwt().get("department_id")
    if not dept_id:
        return fail("Your account has no assigned department.", status=422)

    r = LecturerRequest.query.get(req_id)
    if not r or r.department_id != dept_id:
        return fail("Request not found.", status=404)
    if r.status != "pending_hod":
        return fail("This request has already been decided.", status=409)

    body = json_body()
    if body.get("decision") not in ("approve", "reject"):
        return fail("decision must be 'approve' or 'reject'.", status=422)

    r.status = "pending_admin" if body["decision"] == "approve" else "rejected"
    r.hod_decided_by = get_jwt_identity()
    r.hod_decided_at = datetime.now(timezone.utc)
    r.hod_note = (body.get("note") or "").strip()[:500] or None
    db.session.commit()
    return ok(data=r.to_dict())


@lecturer_requests_bp.patch("/<req_id>/admin-decision")
@service_or_jwt_required("admin")
def admin_decide(req_id):
    r = LecturerRequest.query.get(req_id)
    if not r:
        return fail("Request not found.", status=404)
    if not is_internal_request():
        uni_id = get_jwt_university_id()
        if uni_id and r.department and r.department.university_id != uni_id:
            return fail("Request not found.", status=404)
    if r.status != "pending_admin":
        return fail("This request is not awaiting an admin decision.", status=409)

    body = json_body()
    if body.get("decision") not in ("approve", "reject"):
        return fail("decision must be 'approve' or 'reject'.", status=422)

    r.status = "approved" if body["decision"] == "approve" else "rejected"
    r.admin_decided_by = get_jwt_identity()
    r.admin_decided_at = datetime.now(timezone.utc)
    r.admin_note = (body.get("note") or "").strip()[:500] or None
    db.session.commit()
    return ok(data=r.to_dict())
