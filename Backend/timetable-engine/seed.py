"""
Seed script — wipes ALL timetabling data (user accounts in auth_db are untouched)
and inserts a complete, GA-ready dataset for Techville University.

Run inside the container:
    docker-compose exec timetable-engine python seed.py
"""
import uuid
from app import create_app
from app.extensions import db
from app.models.domain import (
    University, Department, Program, StudentGroup,
    Room, Lecturer, Course, TimeSlot, Constraint,
)

app = create_app()


def uid():
    return str(uuid.uuid4())


# Truncation order respects FK dependencies; CASCADE handles the rest.
CLEAR_ORDER = [
    "timetable_snapshots",
    "timetable_entries",
    "timetables",
    "course_student_groups",
    "lecturer_programs",
    "constraints",
    "time_slots",
    "courses",
    "lecturers",
    "rooms",
    "student_groups",
    "programs",
    "template_time_blocks",
    "timetable_templates",
    "departments",
    "universities",
]


def clear():
    print("Clearing timetabling data …")
    for tbl in CLEAR_ORDER:
        try:
            db.session.execute(db.text(f'TRUNCATE TABLE "{tbl}" RESTART IDENTITY CASCADE'))
            print(f"  cleared  {tbl}")
        except Exception as exc:
            db.session.rollback()
            print(f"  skipped  {tbl}: {exc}")
    db.session.commit()
    print("Clear done.\n")


def seed():
    print("Seeding …\n")

    # ── University ────────────────────────────────────────────────────────────
    uni = University(
        id=uid(), name="Techville University", code="TVU",
        address="123 Innovation Drive, Techville",
        website="https://tvu.ac.ke", is_active=True,
    )
    db.session.add(uni)

    # ── Departments ───────────────────────────────────────────────────────────
    cs_dept = Department(
        id=uid(), name="Computer Science & Information Technology",
        code="DCSIT", faculty="Science & Technology",
        university_id=uni.id,
    )
    biz_dept = Department(
        id=uid(), name="Business & Management Studies",
        code="DBM", faculty="Business",
        university_id=uni.id,
    )
    db.session.add_all([cs_dept, biz_dept])

    # ── Programs ──────────────────────────────────────────────────────────────
    bcs = Program(id=uid(), name="Bachelor of Science in Computer Science",
                  code="BCS", department_id=cs_dept.id,
                  academic_level="Bachelor", duration_years=4)
    bit = Program(id=uid(), name="Bachelor of Science in Information Technology",
                  code="BIT", department_id=cs_dept.id,
                  academic_level="Bachelor", duration_years=3)
    bba = Program(id=uid(), name="Bachelor of Business Administration",
                  code="BBA", department_id=biz_dept.id,
                  academic_level="Bachelor", duration_years=3)
    db.session.add_all([bcs, bit, bba])

    # ── Student Groups ────────────────────────────────────────────────────────
    bcs1a = StudentGroup(id=uid(), name="BCS Year 1 Group A", code="BCS-1A",
                         program_id=bcs.id, year_of_study=1, semester=1, student_count=35)
    bcs1b = StudentGroup(id=uid(), name="BCS Year 1 Group B", code="BCS-1B",
                         program_id=bcs.id, year_of_study=1, semester=1, student_count=33)
    bcs2a = StudentGroup(id=uid(), name="BCS Year 2 Group A", code="BCS-2A",
                         program_id=bcs.id, year_of_study=2, semester=1, student_count=30)
    bit1a = StudentGroup(id=uid(), name="BIT Year 1 Group A", code="BIT-1A",
                         program_id=bit.id, year_of_study=1, semester=1, student_count=40)
    bit2a = StudentGroup(id=uid(), name="BIT Year 2 Group A", code="BIT-2A",
                         program_id=bit.id, year_of_study=2, semester=1, student_count=35)
    bba1a = StudentGroup(id=uid(), name="BBA Year 1 Group A", code="BBA-1A",
                         program_id=bba.id, year_of_study=1, semester=1, student_count=45)
    bba1b = StudentGroup(id=uid(), name="BBA Year 1 Group B", code="BBA-1B",
                         program_id=bba.id, year_of_study=1, semester=1, student_count=42)
    bba2a = StudentGroup(id=uid(), name="BBA Year 2 Group A", code="BBA-2A",
                         program_id=bba.id, year_of_study=2, semester=1, student_count=38)
    db.session.add_all([bcs1a, bcs1b, bcs2a, bit1a, bit2a, bba1a, bba1b, bba2a])

    # ── Rooms ─────────────────────────────────────────────────────────────────
    rooms = [
        Room(id=uid(), name="Lecture Theater A",  code="LT-A",
             capacity=150, room_type="lecture_hall",
             has_projector=True, has_lab_equipment=False, is_available=True),
        Room(id=uid(), name="Lecture Theater B",  code="LT-B",
             capacity=100, room_type="lecture_hall",
             has_projector=True, has_lab_equipment=False, is_available=True),
        Room(id=uid(), name="Classroom 101",      code="CR-101",
             capacity=50, room_type="classroom",
             has_projector=True, has_lab_equipment=False, is_available=True),
        Room(id=uid(), name="Classroom 102",      code="CR-102",
             capacity=50, room_type="classroom",
             has_projector=True, has_lab_equipment=False, is_available=True),
        Room(id=uid(), name="Classroom 201",      code="CR-201",
             capacity=45, room_type="classroom",
             has_projector=True, has_lab_equipment=False, is_available=True),
        Room(id=uid(), name="Classroom 202",      code="CR-202",
             capacity=45, room_type="classroom",
             has_projector=True, has_lab_equipment=False, is_available=True),
        Room(id=uid(), name="Computer Lab 1",     code="LAB-1",
             capacity=40, room_type="lab",
             has_projector=True, has_lab_equipment=True,  is_available=True),
        Room(id=uid(), name="Computer Lab 2",     code="LAB-2",
             capacity=38, room_type="lab",
             has_projector=True, has_lab_equipment=True,  is_available=True),
    ]
    db.session.add_all(rooms)

    # ── Lecturers ─────────────────────────────────────────────────────────────
    alice = Lecturer(id=uid(), name="Dr. Alice Kamau",     email="a.kamau@tvu.ac.ke",
                     staff_id="TVU-001", department_id=cs_dept.id,
                     specialization="Data Structures & Algorithms",
                     max_hours_per_week=18, is_active=True)
    bob   = Lecturer(id=uid(), name="Dr. Bob Odhiambo",    email="b.odhiambo@tvu.ac.ke",
                     staff_id="TVU-002", department_id=cs_dept.id,
                     specialization="Database Systems",
                     max_hours_per_week=18, is_active=True)
    carol = Lecturer(id=uid(), name="Dr. Carol Wanjiru",   email="c.wanjiru@tvu.ac.ke",
                     staff_id="TVU-003", department_id=cs_dept.id,
                     specialization="Software Engineering",
                     max_hours_per_week=18, is_active=True)
    david = Lecturer(id=uid(), name="Prof. David Mwenda",  email="d.mwenda@tvu.ac.ke",
                     staff_id="TVU-004", department_id=cs_dept.id,
                     specialization="Computer Networks",
                     max_hours_per_week=20, is_active=True)
    eve   = Lecturer(id=uid(), name="Dr. Eve Akinyi",      email="e.akinyi@tvu.ac.ke",
                     staff_id="TVU-005", department_id=cs_dept.id,
                     specialization="Programming & Web Development",
                     max_hours_per_week=18, is_active=True)
    frank = Lecturer(id=uid(), name="Dr. Frank Kiplagat",  email="f.kiplagat@tvu.ac.ke",
                     staff_id="TVU-006", department_id=biz_dept.id,
                     specialization="Business Analytics",
                     max_hours_per_week=18, is_active=True)
    grace = Lecturer(id=uid(), name="Prof. Grace Adhiambo",email="g.adhiambo@tvu.ac.ke",
                     staff_id="TVU-007", department_id=biz_dept.id,
                     specialization="Economics & Finance",
                     max_hours_per_week=20, is_active=True)
    henry = Lecturer(id=uid(), name="Dr. Henry Wainaina",  email="h.wainaina@tvu.ac.ke",
                     staff_id="TVU-008", department_id=biz_dept.id,
                     specialization="Management & Strategy",
                     max_hours_per_week=18, is_active=True)
    db.session.add_all([alice, bob, carol, david, eve, frank, grace, henry])

    # flush so we have IDs before building course relationships
    db.session.flush()

    # ── Courses ───────────────────────────────────────────────────────────────
    # Each entry: (code, name, dept, prog, lecturer, yr, sem, hrs, count, lab, prio, [groups])
    courses_spec = [
        # ── BCS Year 1 Sem 1 ── groups: bcs1a, bcs1b
        ("CS101", "Introduction to Programming",  cs_dept, bcs, eve,   1, 1, 4, 35, True,  2, [bcs1a, bcs1b]),
        ("CS102", "Discrete Mathematics",          cs_dept, bcs, alice, 1, 1, 3, 35, False, 2, [bcs1a, bcs1b]),
        ("CS103", "Computer Architecture",         cs_dept, bcs, david, 1, 1, 3, 35, False, 2, [bcs1a, bcs1b]),
        ("CS104", "Communication Skills",          cs_dept, bcs, carol, 1, 1, 2, 35, False, 1, [bcs1a, bcs1b]),
        # ── BCS Year 2 Sem 1 ── group: bcs2a
        ("CS201", "Data Structures & Algorithms",  cs_dept, bcs, alice, 2, 1, 4, 30, False, 3, [bcs2a]),
        ("CS202", "Database Systems I",            cs_dept, bcs, bob,   2, 1, 3, 30, True,  3, [bcs2a]),
        ("CS203", "Software Engineering",          cs_dept, bcs, carol, 2, 1, 3, 30, False, 3, [bcs2a]),
        ("CS204", "Computer Networks",             cs_dept, bcs, david, 2, 1, 3, 30, False, 3, [bcs2a]),
        # ── BIT Year 1 Sem 1 ── group: bit1a
        ("IT101", "Fundamentals of Computing",     cs_dept, bit, eve,   1, 1, 3, 40, False, 2, [bit1a]),
        ("IT102", "Web Technologies",              cs_dept, bit, bob,   1, 1, 3, 40, True,  2, [bit1a]),
        ("IT103", "Data Communications",           cs_dept, bit, david, 1, 1, 3, 40, False, 2, [bit1a]),
        ("IT104", "IT Project Management",         cs_dept, bit, carol, 1, 1, 2, 40, False, 1, [bit1a]),
        # ── BIT Year 2 Sem 1 ── group: bit2a
        ("IT201", "Systems Analysis & Design",     cs_dept, bit, carol, 2, 1, 3, 35, False, 3, [bit2a]),
        ("IT202", "Database Administration",       cs_dept, bit, bob,   2, 1, 4, 35, True,  3, [bit2a]),
        # ── BBA Year 1 Sem 1 ── groups: bba1a, bba1b
        ("BA101", "Introduction to Business",      biz_dept, bba, grace, 1, 1, 3, 45, False, 2, [bba1a, bba1b]),
        ("BA102", "Principles of Economics",       biz_dept, bba, grace, 1, 1, 3, 45, False, 2, [bba1a, bba1b]),
        ("BA103", "Business Mathematics",          biz_dept, bba, frank, 1, 1, 3, 45, False, 2, [bba1a, bba1b]),
        # ── BBA Year 2 Sem 1 ── group: bba2a
        ("BA201", "Business Analytics",            biz_dept, bba, frank, 2, 1, 3, 38, False, 3, [bba2a]),
        ("BA202", "Strategic Management",          biz_dept, bba, henry, 2, 1, 3, 38, False, 3, [bba2a]),
        ("BA203", "Managerial Economics",          biz_dept, bba, grace, 2, 1, 3, 38, False, 3, [bba2a]),
    ]

    for (code, name, dept, prog, lec, yr, sem, hrs, cnt, lab, prio, grps) in courses_spec:
        c = Course(
            id=uid(), code=code, name=name,
            department_id=dept.id, program_id=prog.id, lecturer_id=lec.id,
            year_of_study=yr, semester=sem, weekly_hours=hrs,
            student_count=cnt, requires_lab=lab, priority=prio,
            credit_hours=hrs, course_type="core", is_active=True,
        )
        db.session.add(c)
        db.session.flush()
        c.student_groups = grps

    # ── Time Slots (Mon–Fri, 9 periods/day including lunch) ───────────────────
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    periods = [
        ("08:00", "09:00", "class",  False, "Period 1"),
        ("09:00", "10:00", "class",  False, "Period 2"),
        ("10:00", "11:00", "class",  False, "Period 3"),
        ("11:00", "12:00", "class",  False, "Period 4"),
        ("12:00", "13:00", "lunch",  True,  "Lunch Break"),
        ("13:00", "14:00", "class",  False, "Period 5"),
        ("14:00", "15:00", "class",  False, "Period 6"),
        ("15:00", "16:00", "class",  False, "Period 7"),
        ("16:00", "17:00", "class",  False, "Period 8"),
    ]
    idx = 0
    for day in days:
        for (start, end, stype, is_brk, label) in periods:
            db.session.add(TimeSlot(
                id=uid(), day=day, start_time=start, end_time=end,
                slot_type=stype, is_break=is_brk, label=label,
                slot_index=idx, academic_year="2025/2026",
            ))
            idx += 1

    # ── Constraints ───────────────────────────────────────────────────────────
    db.session.add_all([
        Constraint(
            id=uid(), name="Protect Lunch Break",
            constraint_type="hard", category="time",
            rule_type="lunch_break_protection",
            university_id=uni.id, weight=1.0,
            config={"start": "12:00", "end": "13:00"},
            is_active=True,
        ),
        Constraint(
            id=uid(), name="No Friday Afternoon Classes",
            constraint_type="soft", category="time",
            rule_type="avoid_friday_afternoon",
            university_id=uni.id, weight=0.7,
            config={"days": ["Friday"], "after_hour": 14},
            is_active=True,
        ),
        Constraint(
            id=uid(), name="Max 4 Consecutive Hours per Lecturer",
            constraint_type="soft", category="lecturer",
            rule_type="max_consecutive_hours",
            university_id=uni.id, weight=0.9,
            config={"max_hours": 4},
            is_active=True,
        ),
        Constraint(
            id=uid(), name="Respect Room Capacity",
            constraint_type="hard", category="room",
            rule_type="capacity_check",
            university_id=uni.id, weight=1.0,
            config={},
            is_active=True,
        ),
    ])

    db.session.commit()

    # ── Summary ───────────────────────────────────────────────────────────────
    print("Seed complete!\n")
    print(f"  University  : {uni.name} ({uni.code})")
    print(f"  Departments : {Department.query.count()}")
    print(f"  Programs    : {Program.query.count()}")
    print(f"  Groups      : {StudentGroup.query.count()}")
    print(f"  Rooms       : {Room.query.count()}")
    print(f"  Lecturers   : {Lecturer.query.count()}")
    print(f"  Courses     : {Course.query.count()}")
    print(f"  Time slots  : {TimeSlot.query.count()}")
    print(f"  Constraints : {Constraint.query.count()}")
    print()
    print("The system is ready for timetable generation.")
    print("Go to Generate → select a department/program → run the GA.")


with app.app_context():
    clear()
    seed()
