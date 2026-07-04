from flask import Blueprint, request

from app.extensions import db
from app.models.domain import TimetableComment
from app.security import get_jwt_university_id, service_or_jwt_required
from app.utils.responses import fail, json_body, ok

admin_comments_bp = Blueprint("admin_comments", __name__, url_prefix="/api/v1/admin/comments")


@admin_comments_bp.get("/")
@service_or_jwt_required("admin", "timetable_officer")
def list_admin_comments():
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    status = request.args.get("status")

    query = TimetableComment.query
    uni_id = get_jwt_university_id()
    if uni_id:
        from app.models.domain import Timetable, Department

        query = (
            query.join(Timetable, TimetableComment.timetable_id == Timetable.id)
            .join(Department, Timetable.department_id == Department.id)
            .filter(Department.university_id == uni_id)
        )
    if status:
        query = query.filter(TimetableComment.status == status)

    pagination = query.order_by(TimetableComment.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return ok(
        data=[c.to_dict(include_context=True) for c in pagination.items],
        extra={
            "meta": {
                "page": page,
                "per_page": per_page,
                "total": pagination.total,
                "pages": pagination.pages,
            },
        },
    )


@admin_comments_bp.patch("/<comment_id>")
@service_or_jwt_required("admin", "timetable_officer")
def update_admin_comment(comment_id):
    comment = TimetableComment.query.get(comment_id)
    if not comment:
        return fail("Comment not found.", status=404)

    body = json_body()
    if "status" in body:
        status = body["status"]
        if status not in ("visible", "hidden"):
            return fail("status must be visible or hidden.", status=422)
        comment.status = status
    if "admin_reply" in body:
        reply = (body.get("admin_reply") or "").strip()
        if len(reply) > 500:
            return fail("Reply must be 500 characters or fewer.", status=422)
        comment.admin_reply = reply or None

    db.session.commit()
    return ok(data=comment.to_dict(include_context=True))
