from flask import Blueprint, request
from flask_jwt_extended import get_jwt, get_jwt_identity

from app.extensions import db
from app.models.domain import StudentGroup, Timetable, TimetableEntry, TimetableComment
from app.security import portal_jwt_required
from app.utils.responses import fail, json_body, ok

portal_bp = Blueprint("portal", __name__, url_prefix="/api/v1/portal")


def _entry_portal_dict(entry: TimetableEntry) -> dict:
    data = entry.to_dict()
    tt = entry.timetable
    if tt:
        data["semester"] = tt.semester
        data["timetable_name"] = tt.name
        data["academic_year"] = tt.academic_year
    return data


def _active_timetables_for_group(student_group_id: str) -> list[Timetable]:
    """All active timetables the student may view for their department/program."""
    group = db.session.get(StudentGroup, student_group_id)
    if not group:
        return []

    department_id = group.program.department_id if group.program else None
    if department_id:
        query = Timetable.query.filter(
            Timetable.status == "active",
            Timetable.department_id == department_id,
        )
        if group.program_id:
            query = query.filter(
                db.or_(
                    Timetable.program_id.is_(None),
                    Timetable.program_id == group.program_id,
                )
            )
        return query.order_by(
            Timetable.semester.asc(),
            Timetable.academic_year.desc(),
        ).all()

    return (
        db.session.query(Timetable)
        .join(TimetableEntry, TimetableEntry.timetable_id == Timetable.id)
        .filter(
            TimetableEntry.student_group_id == student_group_id,
            Timetable.status == "active",
        )
        .group_by(Timetable.id)
        .order_by(Timetable.semester.asc(), Timetable.academic_year.desc())
        .all()
    )


def _portal_entries_query(
    student_group_id: str,
    semester: int | None = None,
    timetable_id: str | None = None,
):
    query = (
        TimetableEntry.query.join(Timetable)
        .filter(
            TimetableEntry.student_group_id == student_group_id,
            Timetable.status == "active",
        )
    )
    if timetable_id:
        query = query.filter(Timetable.id == timetable_id)
    elif semester is not None:
        query = query.filter(Timetable.semester == semester)
    return query.order_by(Timetable.semester.asc(), TimetableEntry.time_slot_id)


@portal_bp.get("/timetable/semesters")
@portal_jwt_required
def portal_timetable_semesters():
    claims = get_jwt()
    student_group_id = claims.get("student_group_id")
    if not student_group_id:
        return fail("Student group not found on portal session.", status=422)

    timetables = _active_timetables_for_group(student_group_id)
    return ok(data=[
        {
            "semester": tt.semester,
            "timetable_id": tt.id,
            "name": tt.name,
            "academic_year": tt.academic_year,
        }
        for tt in timetables
    ])


@portal_bp.get("/timetable")
@portal_jwt_required
def portal_timetable():
    claims = get_jwt()
    student_group_id = claims.get("student_group_id")
    if not student_group_id:
        return fail("Student group not found on portal session.", status=422)

    timetable_id = request.args.get("timetable_id")
    semester = request.args.get("semester", type=int)
    entries = _portal_entries_query(student_group_id, semester, timetable_id).all()
    return ok(data=[_entry_portal_dict(e) for e in entries])


@portal_bp.get("/comments")
@portal_jwt_required
def list_portal_comments():
    user_id = get_jwt_identity()
    comments = (
        TimetableComment.query.filter_by(student_user_id=user_id, status="visible")
        .order_by(TimetableComment.created_at.desc())
        .limit(100)
        .all()
    )
    return ok(data=[c.to_dict(include_context=True) for c in comments])


@portal_bp.post("/comments")
@portal_jwt_required
def create_portal_comment():
    claims = get_jwt()
    body = json_body()
    entry_id = body.get("entry_id")
    text = (body.get("body") or "").strip()
    if not entry_id:
        return fail("entry_id is required.", status=422)
    if not text:
        return fail("Comment text is required.", status=422)
    if len(text) > 500:
        return fail("Comment must be 500 characters or fewer.", status=422)

    entry = TimetableEntry.query.get(entry_id)
    if not entry:
        return fail("Timetable entry not found.", status=404)
    if entry.student_group_id and entry.student_group_id != claims.get("student_group_id"):
        return fail("You can only comment on sessions for your group.", status=403)

    comment = TimetableComment(
        entry_id=entry.id,
        timetable_id=entry.timetable_id,
        student_user_id=get_jwt_identity(),
        registration_number=claims.get("registration_number"),
        student_name=f"{claims.get('first_name', '')} {claims.get('last_name', '')}".strip(),
        body=text,
    )
    db.session.add(comment)
    db.session.commit()
    return ok(data=comment.to_dict(include_context=True), status=201)
