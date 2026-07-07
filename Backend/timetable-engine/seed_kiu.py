#!/usr/bin/env python3
"""
Kampala International University seeder — ADDITIVE ONLY.

Creates one new University ("Kampala International University", code "KIU")
with a full, realistic multi-faculty dataset (departments, buildings, rooms,
lecturers, programmes, student groups, courses) at a "medium realistic"
scale. Unlike seed_fresh.py, this NEVER wipes existing data — it is safe to
run alongside any other data already in the database, and safe to re-run
(idempotent via get_or_create on natural keys).

Run:  docker compose exec timetable-engine python seed_kiu.py
Then: docker compose exec auth-service python seed_kiu_users.py
"""
import sys, os, random
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db
from app.models.domain import (
    Building, Course, Department, Lecturer, Program, Room, StudentGroup,
    University,
)

random.seed(42)  # deterministic output across re-runs

UNI_ID = "b0000001-0000-0000-0000-000000000001"  # shared with seed_kiu_users.py

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_or_create(model, lookup_fields, **extra):
    """Return existing instance or create new one. Flushes to get PK."""
    instance = model.query.filter_by(**lookup_fields).first()
    if instance:
        return instance, False
    instance = model(**{**lookup_fields, **extra})
    db.session.add(instance)
    db.session.flush()
    return instance, True


# ── Faculties (Department.faculty is a plain label, not its own table) ────────
FAC_COMPUTING = "Faculty of Computing, Management and Social Sciences"

# ── Departments: code -> (name, faculty, lecturer_count) ──────────────────────
# Deliberately just these four — KIU was pared down from an earlier, much
# broader multi-faculty draft to a tighter, richly-populated set.
DEPARTMENTS = {
    "CIT": ("Department of Computing and Information Technology", FAC_COMPUTING, 14),
    "BUS": ("Department of Business and Management", FAC_COMPUTING, 12),
    "PAD": ("Department of Public Administration", FAC_COMPUTING, 8),
    "SOC": ("Department of Social Sciences and Social Work", FAC_COMPUTING, 12),
}
HEAD_NAMES = {
    "CIT": "Dr. John Mushi", "BUS": "Dr. Amina Hassan",
    "PAD": "Dr. Emmanuel Nyerere", "SOC": "Dr. James Msuya",
}

# ── Programmes: dept_code -> [(name, code, level, years)] ─────────────────────
PROGRAMS = {
    "CIT": [
        ("Bachelor of Science in Computer Science", "BCS", "Bachelor", 3),
        ("Bachelor of Information Technology", "BIT", "Bachelor", 3),
        ("Diploma in Computer Science", "DCS", "Diploma", 2),
    ],
    "BUS": [
        ("Bachelor of Business Administration", "BBA", "Bachelor", 3),
        ("Bachelor of Commerce (Accounting)", "BAC", "Bachelor", 3),
        ("Diploma in Business Administration", "DBA", "Diploma", 2),
    ],
    "PAD": [
        ("Bachelor of Public Administration", "BPA", "Bachelor", 3),
        ("Diploma in Public Administration", "DPA", "Diploma", 2),
    ],
    "SOC": [
        ("Bachelor of Social Work", "BSW", "Bachelor", 3),
        ("Bachelor of Arts in Sociology", "BSS", "Bachelor", 3),
        ("Diploma in Social Work", "DSW", "Diploma", 2),
    ],
}

# ── Buildings: code -> name ─────────────────────────────────────────────────
BUILDINGS = {
    "ICT":  "ICT Building",
    "BUS":  "Business & Management Block",
    "PAD":  "Public Administration Block",
    "SOC":  "Social Sciences Block",
    "ADM":  "Main Administration & Hall Block",
    "LIB":  "Library & Seminar Complex",
}

# ── Rooms: building_code -> [(name, room_type, capacity, has_lab_equipment)] ──
ROOM_TEMPLATES = {
    "ICT": [
        ("ICT Lab 1", "lab", 40, True), ("ICT Lab 2", "lab", 40, True),
        ("ICT Lab 3", "lab", 35, True), ("ICT Lab 4", "lab", 35, True),
        ("ICT Lecture Hall 1", "lecture", 100, False), ("ICT Lecture Hall 2", "lecture", 80, False),
        ("ICT Lecture Hall 3", "lecture", 70, False),
    ],
    "BUS": [
        ("Business Lecture Hall 1", "lecture", 120, False), ("Business Lecture Hall 2", "lecture", 100, False),
        ("Business Lecture Hall 3", "lecture", 90, False),
        ("Seminar Room B1", "seminar", 30, False), ("Seminar Room B2", "seminar", 25, False),
    ],
    "PAD": [
        ("Public Admin Lecture Hall 1", "lecture", 100, False), ("Public Admin Lecture Hall 2", "lecture", 80, False),
        ("Public Admin Seminar Room", "seminar", 30, False),
    ],
    "SOC": [
        ("Social Sciences Lecture Hall 1", "lecture", 100, False), ("Social Sciences Lecture Hall 2", "lecture", 80, False),
        ("Social Sciences Seminar Room", "seminar", 30, False), ("Fieldwork Practicum Room", "seminar", 25, False),
    ],
    "ADM": [
        ("Main Hall", "main_hall", 500, False), ("University Auditorium", "auditorium", 300, False),
    ],
    "LIB": [
        ("Seminar Room L1", "seminar", 25, False), ("Seminar Room L2", "seminar", 25, False),
        ("Seminar Room L3", "seminar", 20, False),
    ],
}

# ── Lecturer name pools (East African context, matching the source dataset) ───
FIRST_NAMES = [
    "John", "Peter", "Grace", "Kelvin", "David", "Neema", "Amina", "Daniel", "Elias",
    "Charles", "Happy", "Irene", "Frank", "Victor", "Stephen", "Dennis", "Anna", "James",
    "Benson", "Michael", "Agnes", "Edward", "Richard", "Lucia", "George", "Leonard",
    "Beatrice", "Esther", "Rose", "Joseph", "Emmanuel", "Ruth", "Joyce", "Mary", "Sophia",
    "Lucy", "Kelvin", "Nancy", "Eric", "Faith", "Samuel", "Florence", "Collins", "Vivian",
]
LAST_NAMES = [
    "Mushi", "Mrema", "Kimaro", "Mtei", "Kweka", "Joseph", "Hassan", "Komba", "Mwita",
    "Mwakalinga", "Msuya", "Ngowi", "Mallya", "Charles", "Mboya", "Nyerere", "Mollel",
    "Mhando", "Kileo", "Mbise", "Mgeni", "Wanjiku", "Kamau", "Ndungu", "Otieno", "Wangari",
    "Kariuki", "Chebet", "Rotich", "Sang", "Njoroge", "Mwakyusa", "Magesa", "John",
]
TITLES = ["Dr.", "Dr.", "Dr.", "Prof.", "Mr.", "Ms."]

SPECIALIZATIONS = {
    "CIT": ["Software Engineering", "Database Systems", "Computer Networks", "Artificial Intelligence",
            "Information Security", "Web Technologies", "Data Science", "Systems Analysis",
            "Mobile Development", "Cloud Computing"],
    "BUS": ["Marketing Management", "Financial Management", "Strategic Management", "Entrepreneurship",
            "Human Resource Management", "Accounting", "Procurement", "International Business"],
    "PAD": ["Public Policy", "Governance", "Local Government Administration", "Development Administration",
            "Public Sector Management"],
    "SOC": ["Social Work Practice", "Sociology", "Community Development", "Social Policy",
            "Criminology", "Gender Studies"],
}

# ── Course pools: dept_code -> [(name, room_hint, weekly_hours)] ──────────────
# room_hint: "lab" (computer lab), "science_lab", "seminar", or None (any room)
COURSE_POOLS = {
    "CIT": [
        ("Introduction to Computer Science", None, 3), ("Programming Fundamentals", "lab", 4),
        ("Computer Organization and Architecture", None, 3), ("Discrete Mathematics", None, 3),
        ("Communication Skills", None, 2), ("Computer Applications", "lab", 2),
        ("Object Oriented Programming", "lab", 4), ("Data Structures and Algorithms", "lab", 4),
        ("Database Systems", "lab", 3), ("Calculus for Computing", None, 3),
        ("Web Technologies", "lab", 3), ("Entrepreneurship", None, 2),
        ("Operating Systems", None, 4), ("Software Engineering", None, 4),
        ("Computer Networks", "lab", 4), ("Probability and Statistics", None, 3),
        ("Artificial Intelligence", None, 4), ("Mobile Application Development", "lab", 4),
        ("Human Computer Interaction", None, 3), ("Systems Analysis and Design", None, 3),
        ("Research Methods", None, 2), ("Information Security", "lab", 4),
        ("Cloud Computing", "lab", 3), ("Final Year Project", None, 6),
    ],
    "BUS": [
        ("Principles of Management", None, 3), ("Financial Accounting", None, 3),
        ("Business Mathematics", None, 3), ("Microeconomics", None, 3),
        ("Communication Skills", None, 2), ("Marketing Principles", None, 3),
        ("Macroeconomics", None, 3), ("Business Law", None, 3),
        ("Entrepreneurship", None, 2), ("Human Resource Management", None, 3),
        ("Financial Management", None, 3), ("Procurement and Supply Chain", None, 3),
        ("Taxation", None, 3), ("Research Methods", None, 2),
        ("Strategic Management", "seminar", 3), ("Business Ethics", None, 2),
        ("International Business", None, 3), ("Investment Analysis", None, 3),
        ("Project", "seminar", 4),
    ],
    "PAD": [
        ("Introduction to Public Administration", None, 3), ("Political Science", None, 3),
        ("Economics", None, 3), ("Public Finance", None, 3),
        ("Human Resource Management", None, 3), ("Local Government Administration", None, 3),
        ("Policy Analysis", "seminar", 3), ("Research Methods", None, 2),
        ("Public Policy", None, 3), ("Strategic Planning", None, 3),
        ("Governance and Ethics", None, 2), ("Organizational Behaviour", None, 3),
        ("Development Administration", None, 3), ("Public Sector Management", None, 3),
        ("Comparative Public Administration", None, 3), ("Administrative Law", None, 3),
        ("Project Planning and Management", "seminar", 3), ("Leadership and Management", None, 3),
        ("Monitoring and Evaluation", "seminar", 3), ("Communication Skills", None, 2),
        ("Project", "seminar", 4),
    ],
    "SOC": [
        ("Introduction to Sociology", None, 3), ("Social Work Practice", "seminar", 3),
        ("Human Behaviour and the Social Environment", None, 3), ("Community Development", None, 3),
        ("Social Policy", None, 3), ("Social Research Methods", "seminar", 3),
        ("Gender Studies", None, 2), ("Social Welfare Administration", None, 3),
        ("Counselling Skills", "seminar", 3), ("Fieldwork Practicum", "seminar", 4),
        ("Population Studies", None, 2), ("Social Problems and Social Change", None, 3),
        ("Criminology", None, 3), ("Family and Child Welfare", None, 3),
        ("Social Work with Groups", "seminar", 3), ("Human Rights and Social Justice", None, 2),
        ("Community Organizing", "seminar", 3), ("Social Statistics", None, 3),
        ("Social Psychology", None, 3), ("Communication Skills", None, 2),
        ("Project", "seminar", 4),
    ],
}

# A handful of courses to pin to a specific room via fixed_room_id, to exercise
# that constraint end-to-end. (dept_code, course-name-substring, room-name)
FIXED_ROOM_PICKS = [
    ("CIT", "Programming Fundamentals", "ICT Lab 1"),
    ("CIT", "Data Structures and Algorithms", "ICT Lab 2"),
    ("BUS", "Strategic Management", "Seminar Room B1"),
    ("PAD", "Policy Analysis", "Public Admin Seminar Room"),
    ("SOC", "Fieldwork Practicum", "Fieldwork Practicum Room"),
]

COURSES_PER_SEMESTER = 6  # every student group gets 6 courses/semester (>5, per requirement)


def make_lecturer_name(used_names):
    while True:
        name = f"{random.choice(TITLES)} {random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        if name not in used_names:
            used_names.add(name)
            return name


def seed():
    app = create_app("production")
    with app.app_context():
        print("\n=== Kampala International University Seeder (additive) ===\n")

        uni, created = get_or_create(
            University, {"code": "KIU"},
            id=UNI_ID, name="Kampala International University",
            address="P.O. Box 20000, Kampala / Dar es Salaam Campus",
            website="https://kiu.ac.ug", is_active=True,
        )
        print(f"University: {uni.name} ({'created' if created else 'already existed'})")

        # ── Buildings ─────────────────────────────────────────────────────────
        print("Creating buildings…")
        building_objs = {}
        for code, name in BUILDINGS.items():
            b, _ = get_or_create(Building, {"name": name, "university_id": uni.id}, code=code)
            building_objs[code] = b
        db.session.flush()

        # ── Rooms ────────────────────────────────────────────────────────────
        print("Creating rooms…")
        room_objs_by_name = {}
        for bcode, rooms in ROOM_TEMPLATES.items():
            building = building_objs[bcode]
            for room_idx, (name, room_type, capacity, has_lab_eq) in enumerate(rooms, start=1):
                code = f"KIU-{bcode}-{room_idx:02d}"
                room, _ = get_or_create(
                    Room, {"code": code},
                    name=name, capacity=capacity, room_type=room_type,
                    building=building.name, building_id=building.id,
                    floor=random.randint(1, 3), has_projector=True,
                    has_lab_equipment=has_lab_eq, is_available=True,
                    university_id=uni.id,
                )
                room_objs_by_name[name] = room
        db.session.flush()
        print(f"  {len(room_objs_by_name)} rooms across {len(building_objs)} buildings.")

        # ── Departments ──────────────────────────────────────────────────────
        print("Creating departments…")
        dept_objs = {}
        for code, (name, faculty, _n_lect) in DEPARTMENTS.items():
            dept, _ = get_or_create(
                Department, {"code": code, "university_id": uni.id},
                name=name, faculty=faculty, head_name=HEAD_NAMES.get(code),
            )
            dept_objs[code] = dept
        db.session.flush()

        # ── Lecturers ────────────────────────────────────────────────────────
        print("Creating lecturers…")
        used_names = set()
        lecturers_by_dept = {}
        staff_counter = 1
        phone_counter = 1
        for dept_code, (_, _, n_lect) in DEPARTMENTS.items():
            dept = dept_objs[dept_code]
            pool = SPECIALIZATIONS.get(dept_code, ["General Studies"])
            dept_lects = []
            for i in range(n_lect):
                name = make_lecturer_name(used_names)
                slug = name.lower().replace("dr.", "dr").replace("prof.", "prof").replace("mr.", "mr").replace("ms.", "ms")
                slug = "".join(ch for ch in slug if ch.isalnum() or ch == " ").strip().replace(" ", ".")
                email = f"{slug}.{staff_counter}@kiu.ac.ug"
                lect, _ = get_or_create(
                    Lecturer, {"email": email},
                    name=name, phone=f"+256700{phone_counter:06d}",
                    staff_id=f"KIU-L{staff_counter:03d}",
                    department_id=dept.id, specialization=random.choice(pool),
                    max_hours_per_week=random.choice([12, 14, 16, 18]),
                    is_active=True,
                )
                dept_lects.append(lect)
                staff_counter += 1
                phone_counter += 1
            lecturers_by_dept[dept_code] = dept_lects
        db.session.flush()
        print(f"  {staff_counter - 1} lecturers across {len(dept_objs)} departments.")

        # ── Programmes + Student Groups ──────────────────────────────────────
        print("Creating programmes and student groups…")
        prog_objs = {}
        group_count = 0
        BIG_FIRST_YEAR = {"BCS", "BBA", "BPA", "BSW"}  # one flagship program per dept, split A/B in year 1
        for dept_code, programs in PROGRAMS.items():
            dept = dept_objs[dept_code]
            for name, code, level, years in programs:
                prog, _ = get_or_create(
                    Program, {"code": code, "department_id": dept.id},
                    name=name, academic_level=level, duration_years=years, is_active=True,
                )
                prog_objs[code] = prog

                for year in range(1, years + 1):
                    # One cohort per year (same students all year, just different
                    # courses per semester) — split years get a Group A/B suffix,
                    # everyone else has a plain "{code} Year {year}" name.
                    letters = ("A", "B") if (code in BIG_FIRST_YEAR and year == 1) else ("A",)
                    for letter in letters:
                        split = len(letters) > 1
                        gcode = f"{code}-Y{year}{letter}" if split else f"{code}-Y{year}"
                        gname = f"{code} Year {year}" + (f" Group {letter}" if split else "")
                        _, was_created = get_or_create(
                            StudentGroup, {"code": gcode, "program_id": prog.id},
                            name=gname,
                            year_of_study=year, semester=1,
                            student_count=random.randint(25, 45), is_active=True,
                        )
                        if was_created:
                            group_count += 1
        db.session.flush()
        print(f"  {len(prog_objs)} programmes, {group_count} student groups.")

        # ── Courses ──────────────────────────────────────────────────────────
        print("Creating courses…")
        course_count = 0
        for dept_code, programs in PROGRAMS.items():
            pool = COURSE_POOLS[dept_code]
            lects = lecturers_by_dept.get(dept_code) or []
            for _, prog_code, _, years in programs:
                prog = prog_objs[prog_code]
                idx = 0
                per_sem = COURSES_PER_SEMESTER
                for year in range(1, years + 1):
                    for semester in (1, 2):
                        groups = StudentGroup.query.filter_by(
                            program_id=prog.id, year_of_study=year
                        ).all()
                        for _ in range(per_sem):
                            name, hint, wh = pool[idx % len(pool)]
                            cycle = idx // len(pool)
                            if cycle == 1:
                                name = f"{name} II"
                            elif cycle >= 2:
                                name = f"{name} III"
                            idx += 1

                            code = f"{prog_code}{year}{idx:02d}"
                            lect = lects[idx % len(lects)] if lects else None
                            required_type = hint  # None, "lab", "science_lab", or "seminar"

                            existing = Course.query.filter_by(code=code).first()
                            if existing:
                                continue
                            course = Course(
                                name=name, code=code,
                                department_id=dept_objs[dept_code].id, program_id=prog.id,
                                lecturer_id=lect.id if lect else None,
                                semester=semester, year_of_study=year,
                                credit_hours=min(wh, 6), weekly_hours=wh,
                                # Each group is scheduled into its own separate room/session, so
                                # this must reflect a single group's size, not the sum across groups.
                                student_count=(max(g.student_count for g in groups) if groups else 30),
                                required_room_type=required_type,
                                requires_lab=(required_type == "lab"),
                                course_type="core", priority=1, is_active=True,
                            )
                            db.session.add(course)
                            db.session.flush()
                            for g in groups:
                                course.student_groups.append(g)
                            course_count += 1
        db.session.flush()
        print(f"  {course_count} courses created.")

        # ── Pin a handful of courses to a specific room ─────────────────────
        print("Pinning a few courses to fixed rooms…")
        pinned = 0
        for dept_code, name_substr, room_name in FIXED_ROOM_PICKS:
            room = room_objs_by_name.get(room_name)
            if not room:
                continue
            course = Course.query.filter(
                Course.department_id == dept_objs[dept_code].id,
                Course.name.like(f"%{name_substr}%"),
            ).first()
            if not course:
                continue
            course.fixed_room_id = room.id
            course.required_room_type = room.room_type
            course.requires_lab = (room.room_type == "lab")
            pinned += 1
        db.session.commit()
        print(f"  {pinned} courses pinned to a fixed room.")

        # ── Summary ──────────────────────────────────────────────────────────
        print("\n=== KIU seed complete ===")
        print(f"  University ID:  {uni.id}")
        print(f"  Departments:    {len(dept_objs)}")
        print(f"  Buildings:      {len(building_objs)}")
        print(f"  Rooms:          {len(room_objs_by_name)}")
        print(f"  Lecturers:      {staff_counter - 1}")
        print(f"  Programmes:     {len(prog_objs)}")
        print(f"  Student groups: {group_count}")
        print(f"  Courses:        {course_count}")
        print()
        print("Next: docker compose exec auth-service python seed_kiu_users.py")


if __name__ == "__main__":
    seed()
