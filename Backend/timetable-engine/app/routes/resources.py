"""CRUD routes for Universities, Departments, Programs, StudentGroups, Rooms,
Lecturers, Courses, TimeSlots, TimetableTemplates, and Constraints."""
from flask import Blueprint, request
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.models.domain import (
    Constraint, Course, Department, Lecturer, Program,
    Room, StudentGroup, TimeSlot, TimetableTemplate, TemplateTimeBlock,
    TimetableEntry, University,
)
from app.security import service_or_jwt_required
from app.utils.responses import fail, json_body, ok

resources_bp = Blueprint("resources", __name__, url_prefix="/api/v1")

WRITE_ROLES = ("admin", "timetable_officer", "hod")


def _create(instance):
    db.session.add(instance)
    db.session.commit()
    return instance


def _update(instance, payload: dict, allowed_fields: tuple[str, ...]):
    for key in allowed_fields:
        if key in payload:
            setattr(instance, key, payload[key])
    db.session.commit()
    return instance


def _dynamic_update(instance, payload: dict):
    """Keep legacy behavior: apply any attribute present on the model instance."""
    for key, value in payload.items():
        if hasattr(instance, key):
            setattr(instance, key, value)
    db.session.commit()
    return instance


def _delete(instance):
    db.session.delete(instance)
    db.session.commit()


# Universities — GET is public so the registration form can list them without a token
@resources_bp.get("/universities")
def list_universities():
    unis = University.query.filter_by(is_active=True).all()
    return ok(data=[u.to_dict() for u in unis])


@resources_bp.post("/universities")
@service_or_jwt_required(*WRITE_ROLES)
def create_university():
    body = json_body()
    uni = University(
        name=body["name"],
        code=body["code"],
        address=body.get("address"),
        website=body.get("website"),
        logo_url=body.get("logo_url"),
    )
    _create(uni)
    return ok(data=uni.to_dict(), status=201)


@resources_bp.put("/universities/<uni_id>")
@service_or_jwt_required(*WRITE_ROLES)
def update_university(uni_id):
    uni = University.query.get_or_404(uni_id)
    _update(uni, json_body(), ("name", "code", "address", "website", "logo_url", "is_active"))
    return ok(data=uni.to_dict())


@resources_bp.delete("/universities/<uni_id>")
@service_or_jwt_required(*WRITE_ROLES)
def delete_university(uni_id):
    uni = University.query.get_or_404(uni_id)
    uni.is_active = False
    db.session.commit()
    return ok(message="University deactivated.")


# Programs
@resources_bp.get("/programs")
@service_or_jwt_required()
def list_programs():
    department_id = request.args.get("department_id")
    university_id = request.args.get("university_id")
    query = Program.query.options(
        joinedload(Program.department).joinedload(Department.university)
    ).filter_by(is_active=True)
    if department_id:
        query = query.filter_by(department_id=department_id)
    if university_id:
        query = query.join(Department).filter(Department.university_id == university_id)
    return ok(data=[p.to_dict() for p in query.all()])


@resources_bp.post("/programs")
@service_or_jwt_required(*WRITE_ROLES)
def create_program():
    body = json_body()
    program = Program(
        name=body["name"],
        code=body["code"],
        department_id=body["department_id"],
        academic_level=body.get("academic_level", "Bachelor"),
        duration_years=body.get("duration_years", 3),
        description=body.get("description"),
    )
    _create(program)
    return ok(data=program.to_dict(), status=201)


@resources_bp.put("/programs/<prog_id>")
@service_or_jwt_required(*WRITE_ROLES)
def update_program(prog_id):
    program = Program.query.get_or_404(prog_id)
    _update(program, json_body(), ("name", "code", "academic_level", "duration_years", "description", "is_active"))
    return ok(data=program.to_dict())


@resources_bp.delete("/programs/<prog_id>")
@service_or_jwt_required(*WRITE_ROLES)
def delete_program(prog_id):
    program = Program.query.get_or_404(prog_id)
    program.is_active = False
    db.session.commit()
    return ok(message="Program deactivated.")


@resources_bp.post("/programs/<prog_id>/lecturers")
@service_or_jwt_required(*WRITE_ROLES)
def assign_lecturer_to_program(prog_id):
    program = Program.query.get_or_404(prog_id)
    body = json_body()
    lecturer_id = body.get("lecturer_id")
    lecturer = Lecturer.query.get_or_404(lecturer_id)
    if lecturer not in program.lecturers:
        program.lecturers.append(lecturer)
        db.session.commit()
    return ok(data=program.to_dict())


@resources_bp.delete("/programs/<prog_id>/lecturers/<lec_id>")
@service_or_jwt_required(*WRITE_ROLES)
def remove_lecturer_from_program(prog_id, lec_id):
    program = Program.query.get_or_404(prog_id)
    lecturer = Lecturer.query.get_or_404(lec_id)
    if lecturer in program.lecturers:
        program.lecturers.remove(lecturer)
        db.session.commit()
    return ok(message="Lecturer removed from program.")


# Student Groups
@resources_bp.get("/student-groups")
@service_or_jwt_required()
def list_student_groups():
    program_id = request.args.get("program_id")
    year = request.args.get("year_of_study", type=int)
    semester = request.args.get("semester", type=int)
    query = StudentGroup.query.options(
        joinedload(StudentGroup.program)
    ).filter_by(is_active=True)
    if program_id:
        query = query.filter_by(program_id=program_id)
    if year:
        query = query.filter_by(year_of_study=year)
    if semester:
        query = query.filter_by(semester=semester)
    return ok(data=[g.to_dict() for g in query.all()])


@resources_bp.post("/student-groups")
@service_or_jwt_required(*WRITE_ROLES)
def create_student_group():
    body = json_body()
    group = StudentGroup(
        name=body["name"],
        code=body["code"],
        program_id=body["program_id"],
        year_of_study=body.get("year_of_study", 1),
        semester=body.get("semester", 1),
        student_count=body.get("student_count", 30),
    )
    _create(group)
    return ok(data=group.to_dict(), status=201)


@resources_bp.put("/student-groups/<group_id>")
@service_or_jwt_required(*WRITE_ROLES)
def update_student_group(group_id):
    group = StudentGroup.query.get_or_404(group_id)
    _update(group, json_body(), ("name", "code", "year_of_study", "semester", "student_count", "is_active"))
    return ok(data=group.to_dict())


@resources_bp.delete("/student-groups/<group_id>")
@service_or_jwt_required(*WRITE_ROLES)
def delete_student_group(group_id):
    group = StudentGroup.query.get_or_404(group_id)
    group.is_active = False
    db.session.commit()
    return ok(message="Student group deactivated.")


# Departments
@resources_bp.get("/departments")
@service_or_jwt_required()
def list_departments():
    university_id = request.args.get("university_id")
    query = Department.query.options(joinedload(Department.university))
    if university_id:
        query = query.filter_by(university_id=university_id)
    depts = query.all()
    return ok(data=[d.to_dict() for d in depts])


@resources_bp.post("/departments")
@service_or_jwt_required(*WRITE_ROLES)
def create_department():
    body = json_body()
    dept = Department(
        name=body["name"],
        code=body["code"],
        faculty=body.get("faculty"),
        head_name=body.get("head_name"),
        university_id=body.get("university_id"),
    )
    _create(dept)
    return ok(data=dept.to_dict(), status=201)


@resources_bp.put("/departments/<dept_id>")
@service_or_jwt_required(*WRITE_ROLES)
def update_department(dept_id):
    dept = Department.query.get_or_404(dept_id)
    _update(dept, json_body(), ("name", "code", "faculty", "head_name", "university_id"))
    return ok(data=dept.to_dict())


@resources_bp.delete("/departments/<dept_id>")
@service_or_jwt_required(*WRITE_ROLES)
def delete_department(dept_id):
    dept = Department.query.get_or_404(dept_id)
    _delete(dept)
    return ok(message="Deleted.")


# Rooms
@resources_bp.get("/rooms")
@service_or_jwt_required()
def list_rooms():
    rooms = Room.query.all()
    return ok(data=[r.to_dict() for r in rooms])


@resources_bp.post("/rooms")
@service_or_jwt_required(*WRITE_ROLES)
def create_room():
    body = json_body()
    room = Room(**{k: body[k] for k in body if k in Room.__table__.columns.keys()})
    _create(room)
    return ok(data=room.to_dict(), status=201)


@resources_bp.put("/rooms/<room_id>")
@service_or_jwt_required(*WRITE_ROLES)
def update_room(room_id):
    room = Room.query.get_or_404(room_id)
    _dynamic_update(room, json_body())
    return ok(data=room.to_dict())


@resources_bp.delete("/rooms/<room_id>")
@service_or_jwt_required(*WRITE_ROLES)
def delete_room(room_id):
    room = Room.query.get_or_404(room_id)
    _delete(room)
    return ok(message="Deleted.")


# Lecturers
@resources_bp.get("/lecturers")
@service_or_jwt_required()
def list_lecturers():
    lecturers = Lecturer.query.options(joinedload(Lecturer.department)).filter_by(is_active=True).all()
    return ok(data=[l.to_dict() for l in lecturers])


@resources_bp.post("/lecturers")
@service_or_jwt_required(*WRITE_ROLES)
def create_lecturer():
    body = json_body()
    allowed = {
        "name", "email", "phone", "staff_id", "department_id",
        "specialization", "max_hours_per_week", "max_hours_per_day",
        "max_consecutive_hours", "preferred_days", "unavailable_slots",
        "availability", "user_id",
    }
    program_ids = body.pop("program_ids", [])
    lecturer = Lecturer(**{k: body[k] for k in body if k in allowed})
    db.session.add(lecturer)
    db.session.flush()  # get lecturer.id before assigning programs
    if program_ids:
        programs = Program.query.filter(Program.id.in_(program_ids)).all()
        lecturer.programs = programs
    db.session.commit()
    return ok(data=lecturer.to_dict(), status=201)


@resources_bp.put("/lecturers/<lec_id>")
@service_or_jwt_required(*WRITE_ROLES)
def update_lecturer(lec_id):
    lecturer = Lecturer.query.get_or_404(lec_id)
    _dynamic_update(lecturer, json_body())
    return ok(data=lecturer.to_dict())


@resources_bp.delete("/lecturers/<lec_id>")
@service_or_jwt_required(*WRITE_ROLES)
def delete_lecturer(lec_id):
    lecturer = Lecturer.query.get_or_404(lec_id)
    lecturer.is_active = False
    db.session.commit()
    return ok(message="Lecturer deactivated.")


# Courses
@resources_bp.get("/courses")
@service_or_jwt_required()
def list_courses():
    department_id = request.args.get("department_id")
    program_id = request.args.get("program_id")
    semester = request.args.get("semester", type=int)
    year_of_study = request.args.get("year_of_study", type=int)
    query = Course.query.options(
        joinedload(Course.department),
        joinedload(Course.program),
        joinedload(Course.lecturer).joinedload(Lecturer.department),
        selectinload(Course.student_groups),
    ).filter_by(is_active=True)
    if department_id:
        query = query.filter_by(department_id=department_id)
    if program_id:
        query = query.filter_by(program_id=program_id)
    if semester:
        query = query.filter_by(semester=semester)
    if year_of_study:
        query = query.filter_by(year_of_study=year_of_study)
    courses = query.all()
    return ok(data=[c.to_dict() for c in courses])


@resources_bp.post("/courses")
@service_or_jwt_required(*WRITE_ROLES)
def create_course():
    body = json_body()
    allowed = {
        "name", "code", "department_id", "program_id", "lecturer_id",
        "semester", "year_of_study", "credit_hours", "weekly_hours",
        "student_count", "requires_lab", "course_type", "priority",
    }
    course = Course(**{k: body[k] for k in body if k in allowed})
    _create(course)
    return ok(data=course.to_dict(), status=201)


@resources_bp.put("/courses/<course_id>")
@service_or_jwt_required(*WRITE_ROLES)
def update_course(course_id):
    course = Course.query.get_or_404(course_id)
    _dynamic_update(course, json_body())
    return ok(data=course.to_dict())


@resources_bp.delete("/courses/<course_id>")
@service_or_jwt_required(*WRITE_ROLES)
def delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    course.is_active = False
    db.session.commit()
    return ok(message="Course deactivated.")


# Course ↔ StudentGroup assignments
@resources_bp.get("/courses/<course_id>/groups")
@service_or_jwt_required()
def list_course_groups(course_id):
    course = Course.query.get_or_404(course_id)
    return ok(data=[{"id": g.id, "code": g.code, "name": g.name, "student_count": g.student_count} for g in course.student_groups])


@resources_bp.post("/courses/<course_id>/groups")
@service_or_jwt_required(*WRITE_ROLES)
def set_course_groups(course_id):
    """Replace the full set of student groups assigned to a course."""
    course = Course.query.get_or_404(course_id)
    body = json_body()
    group_ids = body.get("group_ids", [])
    groups = StudentGroup.query.filter(StudentGroup.id.in_(group_ids)).all() if group_ids else []
    course.student_groups = groups
    db.session.commit()
    return ok(data=course.to_dict())


@resources_bp.delete("/courses/<course_id>/groups/<group_id>")
@service_or_jwt_required(*WRITE_ROLES)
def remove_course_group(course_id, group_id):
    course = Course.query.get_or_404(course_id)
    group = StudentGroup.query.get_or_404(group_id)
    if group in course.student_groups:
        course.student_groups.remove(group)
        db.session.commit()
    return ok(message="Group removed from course.")


# Substitute a sick/absent lecturer across all entries in a timetable
@resources_bp.post("/timetable/<timetable_id>/substitute-lecturer")
@service_or_jwt_required(*WRITE_ROLES)
def substitute_lecturer(timetable_id):
    body = json_body()
    sick_id = body.get("sick_lecturer_id")
    replacement_id = body.get("replacement_lecturer_id")
    if not sick_id or not replacement_id:
        return fail("sick_lecturer_id and replacement_lecturer_id are required.", status=422)

    replacement = Lecturer.query.get(replacement_id)
    if not replacement or not replacement.is_active:
        return fail("Replacement lecturer not found or inactive.", status=404)

    entries = (
        TimetableEntry.query
        .filter_by(timetable_id=timetable_id, lecturer_id=sick_id)
        .all()
    )
    if not entries:
        return ok(message="No entries found for the sick lecturer in this timetable.", data={"updated": 0})

    for entry in entries:
        entry.lecturer_id = replacement_id
    db.session.commit()
    return ok(data={"updated": len(entries), "replacement": replacement.to_dict()})


# Constraints
@resources_bp.get("/constraints")
@service_or_jwt_required()
def list_constraints():
    category = request.args.get("category")
    rule_type = request.args.get("rule_type")
    constraint_type = request.args.get("constraint_type")
    q = Constraint.query.filter_by(is_active=True)
    if category:
        q = q.filter_by(category=category)
    if rule_type:
        q = q.filter_by(rule_type=rule_type)
    if constraint_type:
        q = q.filter_by(constraint_type=constraint_type)
    return ok(data=[c.to_dict() for c in q.all()])


@resources_bp.post("/constraints")
@service_or_jwt_required(*WRITE_ROLES)
def create_constraint():
    body = json_body()
    constraint = Constraint(
        name=body["name"],
        constraint_type=body.get("constraint_type", "soft"),
        category=body.get("category"),
        rule_type=body.get("rule_type"),
        entity_type=body.get("entity_type"),
        entity_id=body.get("entity_id"),
        university_id=body.get("university_id"),
        department_id=body.get("department_id"),
        weight=body.get("weight", 1.0),
        config=body.get("config", {}),
    )
    _create(constraint)
    return ok(data=constraint.to_dict(), status=201)


@resources_bp.put("/constraints/<constraint_id>")
@service_or_jwt_required(*WRITE_ROLES)
def update_constraint(constraint_id):
    constraint = Constraint.query.get_or_404(constraint_id)
    _update(constraint, json_body(), (
        "name", "constraint_type", "category", "rule_type",
        "entity_type", "entity_id", "university_id", "department_id",
        "weight", "config", "is_active",
    ))
    return ok(data=constraint.to_dict())


@resources_bp.delete("/constraints/<constraint_id>")
@service_or_jwt_required(*WRITE_ROLES)
def delete_constraint(constraint_id):
    constraint = Constraint.query.get_or_404(constraint_id)
    constraint.is_active = False
    db.session.commit()
    return ok(message="Constraint deactivated.")


# Time slots
@resources_bp.get("/time-slots")
@service_or_jwt_required()
def list_time_slots():
    slots = TimeSlot.query.order_by(TimeSlot.slot_index.asc()).all()
    return ok(data=[s.to_dict() for s in slots])


@resources_bp.post("/time-slots")
@service_or_jwt_required(*WRITE_ROLES)
def create_time_slot():
    body = json_body()
    slot = TimeSlot(
        day=body["day"],
        start_time=body["start_time"],
        end_time=body["end_time"],
        slot_index=body.get("slot_index"),
        is_break=body.get("is_break", False),
        academic_year=body.get("academic_year"),
    )
    _create(slot)
    return ok(data=slot.to_dict(), status=201)


@resources_bp.put("/time-slots/<slot_id>")
@service_or_jwt_required(*WRITE_ROLES)
def update_time_slot(slot_id):
    slot = TimeSlot.query.get_or_404(slot_id)
    _update(slot, json_body(), ("day", "start_time", "end_time", "slot_index", "is_break", "academic_year"))
    return ok(data=slot.to_dict())


@resources_bp.delete("/time-slots/<slot_id>")
@service_or_jwt_required(*WRITE_ROLES)
def delete_time_slot(slot_id):
    slot = TimeSlot.query.get_or_404(slot_id)
    _delete(slot)
    return ok(message="Deleted.")


# Timetable Templates
@resources_bp.get("/templates")
@service_or_jwt_required()
def list_templates():
    university_id = request.args.get("university_id")
    q = TimetableTemplate.query
    if university_id:
        q = q.filter_by(university_id=university_id)
    templates = q.all()
    return ok(data=[t.to_dict(include_blocks=True) for t in templates])


@resources_bp.get("/templates/<template_id>")
@service_or_jwt_required()
def get_template(template_id):
    template = TimetableTemplate.query.get_or_404(template_id)
    return ok(data=template.to_dict(include_blocks=True))


@resources_bp.post("/templates")
@service_or_jwt_required(*WRITE_ROLES)
def create_template():
    body = json_body()
    if not body.get("name"):
        return fail("name is required.", status=422)
    template = TimetableTemplate(
        name=body["name"],
        description=body.get("description"),
        university_id=body.get("university_id"),
        is_default=body.get("is_default", False),
        days_of_week=body.get("days_of_week", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]),
    )
    db.session.add(template)
    db.session.flush()

    # Create blocks inline if provided
    for i, blk in enumerate(body.get("blocks", [])):
        db.session.add(TemplateTimeBlock(
            template_id=template.id,
            label=blk["label"],
            start_time=blk["start_time"],
            end_time=blk["end_time"],
            block_type=blk.get("block_type", "class"),
            sort_order=blk.get("sort_order", i),
        ))

    db.session.commit()
    return ok(data=template.to_dict(include_blocks=True), status=201)


@resources_bp.put("/templates/<template_id>")
@service_or_jwt_required(*WRITE_ROLES)
def update_template(template_id):
    template = TimetableTemplate.query.get_or_404(template_id)
    _update(template, json_body(), ("name", "description", "university_id", "is_default", "days_of_week"))
    return ok(data=template.to_dict(include_blocks=True))


@resources_bp.delete("/templates/<template_id>")
@service_or_jwt_required(*WRITE_ROLES)
def delete_template(template_id):
    template = TimetableTemplate.query.get_or_404(template_id)
    _delete(template)
    return ok(message="Template deleted.")


# Template Time Blocks
@resources_bp.get("/templates/<template_id>/blocks")
@service_or_jwt_required()
def list_template_blocks(template_id):
    TimetableTemplate.query.get_or_404(template_id)
    blocks = TemplateTimeBlock.query.filter_by(template_id=template_id).order_by(
        TemplateTimeBlock.sort_order
    ).all()
    return ok(data=[b.to_dict() for b in blocks])


@resources_bp.post("/templates/<template_id>/blocks")
@service_or_jwt_required(*WRITE_ROLES)
def create_template_block(template_id):
    TimetableTemplate.query.get_or_404(template_id)
    body = json_body()
    if not body.get("label") or not body.get("start_time") or not body.get("end_time"):
        return fail("label, start_time and end_time are required.", status=422)
    block = TemplateTimeBlock(
        template_id=template_id,
        label=body["label"],
        start_time=body["start_time"],
        end_time=body["end_time"],
        block_type=body.get("block_type", "class"),
        sort_order=body.get("sort_order", 0),
    )
    _create(block)
    return ok(data=block.to_dict(), status=201)


@resources_bp.put("/templates/<template_id>/blocks/<block_id>")
@service_or_jwt_required(*WRITE_ROLES)
def update_template_block(template_id, block_id):
    block = TemplateTimeBlock.query.filter_by(id=block_id, template_id=template_id).first_or_404()
    _update(block, json_body(), ("label", "start_time", "end_time", "block_type", "sort_order"))
    return ok(data=block.to_dict())


@resources_bp.delete("/templates/<template_id>/blocks/<block_id>")
@service_or_jwt_required(*WRITE_ROLES)
def delete_template_block(template_id, block_id):
    block = TemplateTimeBlock.query.filter_by(id=block_id, template_id=template_id).first_or_404()
    _delete(block)
    return ok(message="Block deleted.")


@resources_bp.post("/templates/<template_id>/generate-slots")
@service_or_jwt_required(*WRITE_ROLES)
def generate_slots_from_template(template_id):
    """
    Generate TimeSlot rows from template blocks for every day in the template.
    Existing slots for this template are replaced.
    """
    template = TimetableTemplate.query.get_or_404(template_id)
    if not template.blocks:
        return fail("Template has no blocks defined.", status=400)

    # Remove old slots for this template
    TimeSlot.query.filter_by(template_id=template_id).delete()

    idx = 0
    for day in (template.days_of_week or ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]):
        for block in template.blocks:
            is_break = block.block_type in ("break", "lunch")
            db.session.add(TimeSlot(
                day=day,
                start_time=block.start_time,
                end_time=block.end_time,
                slot_index=idx,
                is_break=is_break,
                slot_type=block.block_type,
                label=block.label,
                template_id=template_id,
            ))
            idx += 1

    db.session.commit()
    slots = TimeSlot.query.filter_by(template_id=template_id).order_by(TimeSlot.slot_index).all()
    return ok(data=[s.to_dict() for s in slots], extra={"generated": len(slots)})
