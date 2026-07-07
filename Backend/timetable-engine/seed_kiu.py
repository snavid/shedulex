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
FAC_HEALTH = "Faculty of Health Sciences"
FAC_LAW = "Faculty of Law"
FAC_EDUCATION = "Faculty of Education"

# ── Departments: code -> (name, faculty, lecturer_count) ──────────────────────
DEPARTMENTS = {
    "CIT": ("Department of Computing and Information Technology", FAC_COMPUTING, 8),
    "BUS": ("Department of Business and Management", FAC_COMPUTING, 6),
    "SOC": ("Department of Social Sciences and Social Work", FAC_COMPUTING, 4),
    "PAD": ("Department of Public Administration", FAC_COMPUTING, 3),
    "MAT": ("Department of Mathematics and Statistics", FAC_COMPUTING, 3),
    "CLM": ("Department of Clinical Medicine", FAC_HEALTH, 5),
    "PHS": ("Department of Pharmaceutical Sciences", FAC_HEALTH, 4),
    "MLS": ("Department of Medical Laboratory Sciences", FAC_HEALTH, 4),
    "NUR": ("Department of Nursing", FAC_HEALTH, 4),
    "ANA": ("Department of Human Anatomy", FAC_HEALTH, 3),
    "PHY": ("Department of Physiology", FAC_HEALTH, 3),
    "PAT": ("Department of Pathology", FAC_HEALTH, 3),
    "COM": ("Department of Community Medicine", FAC_HEALTH, 2),
    "SUR": ("Department of Surgery", FAC_HEALTH, 3),
    "PED": ("Department of Pediatrics and Obstetrics & Gynaecology", FAC_HEALTH, 3),
    "LAW": ("Department of Legal Studies", FAC_LAW, 4),
    "ARE": ("Department of Arts with Education", FAC_EDUCATION, 2),
    "SCE": ("Department of Science with Education", FAC_EDUCATION, 2),
}
HEAD_NAMES = {
    "CIT": "Dr. John Mushi", "BUS": "Dr. Amina Hassan", "SOC": "Dr. James Msuya",
    "PAD": "Dr. Emmanuel Nyerere", "MAT": "Dr. David Kweka", "CLM": "Dr. Joseph Mwakyusa",
    "PHS": "Dr. Irene Charles", "MLS": "Dr. Lucy Magesa", "NUR": "Dr. Beatrice John",
    "ANA": "Dr. Happy Mboya", "PHY": "Dr. Victor Mwita", "PAT": "Dr. Lucy Magesa",
    "COM": "Dr. Beatrice John", "SUR": "Dr. Daniel Komba", "PED": "Dr. Anna Mushi",
    "LAW": "Dr. Sophia Mollel", "ARE": "Ms. Rose Kileo", "SCE": "Dr. Victor Mushi",
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
    "SOC": [
        ("Bachelor of Social Work", "BSW", "Bachelor", 3),
        ("Bachelor of Arts in Sociology", "SOC", "Bachelor", 3),
        ("Diploma in Social Work", "DSW", "Diploma", 2),
    ],
    "PAD": [
        ("Bachelor of Public Administration", "BPA", "Bachelor", 3),
        ("Diploma in Public Administration", "DPA", "Diploma", 2),
    ],
    "MAT": [
        ("Bachelor of Science in Mathematics and Statistics", "BSM", "Bachelor", 3),
    ],
    "CLM": [
        ("Bachelor of Medicine and Bachelor of Surgery", "MBBS", "Bachelor", 5),
        ("Diploma in Clinical Medicine", "DCM", "Diploma", 3),
    ],
    "PHS": [
        ("Bachelor of Pharmacy", "BPH", "Bachelor", 4),
        ("Diploma in Pharmacy", "DPH", "Diploma", 2),
    ],
    "MLS": [
        ("Bachelor of Science in Medical Laboratory Sciences", "BML", "Bachelor", 3),
    ],
    "NUR": [
        ("Bachelor of Science in Nursing", "BSN", "Bachelor", 3),
        ("Diploma in Nursing", "DNS", "Diploma", 2),
    ],
    "LAW": [
        ("Bachelor of Laws", "LLB", "Bachelor", 3),
        ("Diploma in Law", "DLW", "Diploma", 2),
    ],
    "ARE": [
        ("Bachelor of Arts with Education", "BAE", "Bachelor", 3),
    ],
    "SCE": [
        ("Bachelor of Science with Education", "BSE", "Bachelor", 3),
    ],
}

# ── Buildings: code -> name ─────────────────────────────────────────────────
BUILDINGS = {
    "ICT":  "ICT Building",
    "SCI":  "Science Complex",
    "BUS":  "Business & Management Block",
    "LAW":  "Law Block",
    "MED":  "Medical School Block",
    "PHM":  "Pharmacy Building",
    "NUR":  "Nursing Building",
    "EDU":  "Education Block",
    "ADM":  "Main Administration & Hall Block",
    "SOC":  "Social Sciences Block",
    "LIB":  "Library & Seminar Complex",
}

# ── Rooms: building_code -> [(name, room_type, capacity, has_lab_equipment)] ──
ROOM_TEMPLATES = {
    "ICT": [
        ("ICT Lab 1", "lab", 40, True), ("ICT Lab 2", "lab", 40, True),
        ("ICT Lab 3", "lab", 35, True),
        ("ICT Lecture Hall 1", "lecture", 100, False), ("ICT Lecture Hall 2", "lecture", 80, False),
    ],
    "SCI": [
        ("Science Lab 1", "science_lab", 45, True), ("Science Lab 2", "science_lab", 45, True),
        ("Physics Lab", "science_lab", 40, True), ("Science Lecture Hall", "lecture", 90, False),
    ],
    "BUS": [
        ("Business Lecture Hall 1", "lecture", 120, False), ("Business Lecture Hall 2", "lecture", 100, False),
        ("Seminar Room B1", "seminar", 30, False), ("Seminar Room B2", "seminar", 25, False),
    ],
    "LAW": [
        ("Law Lecture Hall", "lecture", 90, False), ("Moot Court Room", "seminar", 40, False),
        ("Law Seminar Room", "seminar", 25, False),
    ],
    "MED": [
        ("Anatomy Lecture Theatre", "lecture", 150, False), ("Physiology Lab", "science_lab", 50, True),
        ("Pathology Lab", "science_lab", 40, True), ("Medical Lecture Hall 1", "lecture", 120, False),
        ("Medical Lecture Hall 2", "lecture", 100, False), ("Clinical Skills Lab", "science_lab", 35, True),
    ],
    "PHM": [
        ("Pharmacy Lab", "science_lab", 40, True), ("Pharmacy Lecture Hall", "lecture", 80, False),
    ],
    "NUR": [
        ("Nursing Skills Lab", "science_lab", 35, True), ("Nursing Lecture Hall", "lecture", 90, False),
    ],
    "EDU": [
        ("Education Lecture Hall", "lecture", 100, False), ("Education Seminar Room", "seminar", 30, False),
    ],
    "ADM": [
        ("Main Hall", "main_hall", 500, False), ("University Auditorium", "auditorium", 300, False),
    ],
    "SOC": [
        ("Social Sciences Lecture Hall", "lecture", 100, False), ("Social Sciences Seminar Room", "seminar", 30, False),
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
            "Information Security", "Web Technologies", "Data Science", "Systems Analysis"],
    "BUS": ["Marketing Management", "Financial Management", "Strategic Management", "Entrepreneurship",
            "Human Resource Management", "Accounting"],
    "SOC": ["Social Work Practice", "Sociology", "Community Development", "Social Policy"],
    "PAD": ["Public Policy", "Governance", "Local Government Administration"],
    "MAT": ["Applied Mathematics", "Statistics", "Numerical Analysis"],
    "CLM": ["Internal Medicine", "General Practice", "Clinical Diagnostics"],
    "PHS": ["Pharmacology", "Pharmaceutics", "Medicinal Chemistry"],
    "MLS": ["Microbiology", "Hematology", "Clinical Chemistry"],
    "NUR": ["Clinical Nursing", "Community Health Nursing", "Midwifery"],
    "ANA": ["Gross Anatomy", "Histology", "Neuroanatomy"],
    "PHY": ["Human Physiology", "Cell Physiology"],
    "PAT": ["Anatomic Pathology", "Clinical Pathology"],
    "COM": ["Epidemiology", "Public Health"],
    "SUR": ["General Surgery", "Orthopedic Surgery"],
    "PED": ["Pediatrics", "Obstetrics & Gynaecology"],
    "LAW": ["Constitutional Law", "Commercial Law", "Criminal Law", "Human Rights Law"],
    "ARE": ["Curriculum Studies", "Educational Psychology"],
    "SCE": ["Science Education", "Mathematics Education"],
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
    "SOC": [
        ("Introduction to Sociology", None, 3), ("Social Work Practice", "seminar", 3),
        ("Human Behaviour and the Social Environment", None, 3), ("Community Development", None, 3),
        ("Social Policy", None, 3), ("Social Research Methods", "seminar", 3),
        ("Gender Studies", None, 2), ("Social Welfare Administration", None, 3),
        ("Counselling Skills", "seminar", 3), ("Fieldwork Practicum", "seminar", 4),
        ("Population Studies", None, 2), ("Project", "seminar", 4),
    ],
    "PAD": [
        ("Introduction to Public Administration", None, 3), ("Political Science", None, 3),
        ("Economics", None, 3), ("Public Finance", None, 3),
        ("Human Resource Management", None, 3), ("Local Government Administration", None, 3),
        ("Policy Analysis", "seminar", 3), ("Research Methods", None, 2),
        ("Public Policy", None, 3), ("Strategic Planning", None, 3),
        ("Governance and Ethics", None, 2), ("Project", "seminar", 4),
    ],
    "MAT": [
        ("Calculus I", None, 4), ("Linear Algebra", None, 3), ("Discrete Mathematics", None, 3),
        ("Probability Theory", None, 3), ("Calculus II", None, 4), ("Statistical Methods", None, 3),
        ("Numerical Analysis", None, 3), ("Operations Research", None, 3),
        ("Applied Statistics", None, 3), ("Mathematical Modelling", None, 3),
        ("Research Methods", None, 2), ("Project", "seminar", 4),
    ],
    "CLM": [
        ("Human Anatomy I", "science_lab", 4), ("Human Physiology I", "science_lab", 4),
        ("Biochemistry I", "science_lab", 3), ("Medical Ethics", None, 2),
        ("Communication Skills", None, 2), ("Human Anatomy II", "science_lab", 4),
        ("Human Physiology II", "science_lab", 4), ("Biochemistry II", "science_lab", 3),
        ("Community Health", None, 3), ("Pathology", "science_lab", 4),
        ("Pharmacology", "science_lab", 4), ("Microbiology", "science_lab", 4),
        ("Internal Medicine", "science_lab", 5), ("Surgery", "science_lab", 5),
        ("Pediatrics", "science_lab", 4), ("Obstetrics & Gynaecology", "science_lab", 4),
        ("Psychiatry", None, 3), ("Community Medicine", None, 3),
        ("Clinical Rotations", "science_lab", 6), ("Research Project", "seminar", 4),
    ],
    "PHS": [
        ("Human Anatomy", "science_lab", 3), ("Organic Chemistry", "science_lab", 3),
        ("Biochemistry", "science_lab", 3), ("Medical Terminology", None, 2),
        ("Pharmacology", "science_lab", 4), ("Pharmaceutics", "science_lab", 4),
        ("Medicinal Chemistry", "science_lab", 3), ("Microbiology", "science_lab", 3),
        ("Clinical Pharmacy", "science_lab", 4), ("Pharmacokinetics", None, 3),
        ("Toxicology", None, 3), ("Hospital Pharmacy", "science_lab", 3),
        ("Community Pharmacy", None, 3), ("Industrial Pharmacy", "science_lab", 3),
        ("Research Methods", None, 2), ("Project", "seminar", 4),
    ],
    "MLS": [
        ("Human Anatomy and Physiology", "science_lab", 3), ("General Chemistry", "science_lab", 3),
        ("Medical Microbiology", "science_lab", 4), ("Hematology", "science_lab", 4),
        ("Clinical Chemistry", "science_lab", 4), ("Immunology", "science_lab", 3),
        ("Histopathology", "science_lab", 3), ("Parasitology", "science_lab", 3),
        ("Blood Transfusion Science", "science_lab", 3), ("Quality Control in the Lab", None, 2),
        ("Research Methods", None, 2), ("Project", "seminar", 4),
    ],
    "NUR": [
        ("Fundamentals of Nursing", "science_lab", 4), ("Human Anatomy and Physiology", "science_lab", 3),
        ("Medical-Surgical Nursing I", "science_lab", 4), ("Community Health Nursing", None, 3),
        ("Pharmacology for Nurses", None, 3), ("Medical-Surgical Nursing II", "science_lab", 4),
        ("Midwifery", "science_lab", 4), ("Mental Health Nursing", None, 3),
        ("Pediatric Nursing", "science_lab", 3), ("Research Methods", None, 2),
        ("Clinical Practicum", "science_lab", 5), ("Project", "seminar", 4),
    ],
    "LAW": [
        ("Legal Methods", None, 3), ("Constitutional Law", None, 3),
        ("Criminal Law", None, 3), ("Legal Writing", "seminar", 2),
        ("Contract Law", None, 3), ("Land Law", None, 3),
        ("Administrative Law", None, 3), ("Family Law", None, 3),
        ("Research Methods", None, 2), ("Commercial Law", None, 3),
        ("Labour Law", None, 3), ("International Law", None, 3),
        ("Moot Court", "seminar", 3), ("Human Rights Law", None, 3),
        ("Dissertation", "seminar", 4),
    ],
    "ARE": [
        ("Educational Psychology", None, 3), ("Curriculum Studies", None, 3),
        ("Introduction to Literature", None, 3), ("History of East Africa", None, 3),
        ("Teaching Methods", "seminar", 3), ("Geography", None, 3),
        ("Educational Assessment", None, 2), ("Guidance and Counselling", "seminar", 2),
        ("Kiswahili Studies", None, 3), ("Research Methods", None, 2),
        ("Teaching Practice", "seminar", 4), ("Project", "seminar", 4),
    ],
    "SCE": [
        ("Educational Psychology", None, 3), ("Curriculum Studies", None, 3),
        ("General Physics", "science_lab", 3), ("General Chemistry", "science_lab", 3),
        ("Teaching Methods", "seminar", 3), ("General Biology", "science_lab", 3),
        ("Educational Assessment", None, 2), ("Guidance and Counselling", "seminar", 2),
        ("Mathematics for Educators", None, 3), ("Research Methods", None, 2),
        ("Teaching Practice", "seminar", 4), ("Project", "seminar", 4),
    ],
}

# A handful of courses to pin to a specific room via fixed_room_id, to exercise
# that constraint end-to-end. (dept_code, course-name-substring, room-name)
FIXED_ROOM_PICKS = [
    ("CIT", "Programming Fundamentals", "ICT Lab 1"),
    ("PHS", "Pharmaceutics", "Pharmacy Lab"),
    ("MLS", "Hematology", "Science Lab 1"),
    ("LAW", "Moot Court", "Moot Court Room"),
    ("NUR", "Fundamentals of Nursing", "Nursing Skills Lab"),
]

COURSES_PER_SEMESTER = 3  # bachelors/diplomas; MBBS gets more, below


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
        BIG_FIRST_YEAR = {"BCS", "MBBS", "BBA"}  # split into Group A/B in year 1
        for dept_code, programs in PROGRAMS.items():
            dept = dept_objs[dept_code]
            for name, code, level, years in programs:
                prog, _ = get_or_create(
                    Program, {"code": code, "department_id": dept.id},
                    name=name, academic_level=level, duration_years=years, is_active=True,
                )
                prog_objs[code] = prog

                for year in range(1, years + 1):
                    for semester in (1, 2):
                        letters = ("A", "B") if (code in BIG_FIRST_YEAR and year == 1) else ("A",)
                        for letter in letters:
                            gcode = f"{code}-Y{year}S{semester}{letter}"
                            _, was_created = get_or_create(
                                StudentGroup, {"code": gcode, "program_id": prog.id},
                                name=f"{code} Year {year} Sem {semester} Group {letter}",
                                year_of_study=year, semester=semester,
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
                per_sem = 4 if prog_code == "MBBS" else COURSES_PER_SEMESTER
                for year in range(1, years + 1):
                    for semester in (1, 2):
                        groups = StudentGroup.query.filter_by(
                            program_id=prog.id, year_of_study=year, semester=semester
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
