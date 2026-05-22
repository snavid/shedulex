#!/usr/bin/env python3
"""
Comprehensive demo data seeder for the timetable-engine database.
Run from inside the container:  python seed_demo.py
Or from host:  docker compose exec timetable-engine python seed_demo.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db
from app.models.domain import (
    University, Department, Program, StudentGroup,
    Room, Lecturer, Course, TimeSlot
)


# ─── Seed data definitions ────────────────────────────────────────────────────

UNIVERSITIES = [
    {
        "name": "Strathmore University",
        "code": "STR",
        "address": "Ole Sangale Road, Madaraka Estate, Nairobi",
        "website": "https://strathmore.edu",
    },
    {
        "name": "University of Nairobi",
        "code": "UON",
        "address": "Harry Thuku Road, Nairobi",
        "website": "https://uonbi.ac.ke",
    },
]

DEPARTMENTS = {
    "STR": [
        {"name": "Faculty of Information Technology", "code": "FIT", "faculty": "Science and Technology", "head_name": "Prof. Sarah Wanjiku"},
        {"name": "Faculty of Commerce", "code": "FoCom", "faculty": "Business", "head_name": "Dr. Peter Kamau"},
        {"name": "Faculty of Applied Sciences", "code": "FAS", "faculty": "Sciences", "head_name": "Prof. Grace Muthoni"},
    ],
    "UON": [
        {"name": "School of Computing and Informatics", "code": "SCI", "faculty": "Computing", "head_name": "Prof. James Otieno"},
        {"name": "School of Business", "code": "SoB", "faculty": "Business", "head_name": "Dr. Alice Ndungu"},
        {"name": "School of Engineering", "code": "SOE", "faculty": "Engineering", "head_name": "Prof. David Mwangi"},
    ],
}

PROGRAMS = {
    "FIT": [
        {"name": "Bachelor of Computer Science", "code": "BCS", "academic_level": "Bachelor", "duration_years": 4},
        {"name": "Bachelor of Information Technology", "code": "BIT", "academic_level": "Bachelor", "duration_years": 4},
        {"name": "Diploma in Computer Science", "code": "DCS", "academic_level": "Diploma", "duration_years": 2},
    ],
    "FoCom": [
        {"name": "Bachelor of Commerce", "code": "BCom", "academic_level": "Bachelor", "duration_years": 4},
        {"name": "Bachelor of Business Administration", "code": "BBA", "academic_level": "Bachelor", "duration_years": 4},
    ],
    "FAS": [
        {"name": "Bachelor of Science in Mathematics", "code": "BSMath", "academic_level": "Bachelor", "duration_years": 4},
        {"name": "Diploma in Data Science", "code": "DDS", "academic_level": "Diploma", "duration_years": 2},
    ],
    "SCI": [
        {"name": "Bachelor of Science in Computer Science", "code": "BSCS", "academic_level": "Bachelor", "duration_years": 4},
        {"name": "Bachelor of Information Science", "code": "BIS", "academic_level": "Bachelor", "duration_years": 4},
        {"name": "Certificate in IT", "code": "CIT", "academic_level": "Certificate", "duration_years": 1},
    ],
    "SoB": [
        {"name": "Bachelor of Business Management", "code": "BBM", "academic_level": "Bachelor", "duration_years": 4},
        {"name": "Diploma in Business Administration", "code": "DBA", "academic_level": "Diploma", "duration_years": 2},
    ],
    "SOE": [
        {"name": "Bachelor of Science in Electrical Engineering", "code": "BEE", "academic_level": "Bachelor", "duration_years": 5},
        {"name": "Bachelor of Science in Civil Engineering", "code": "BCE", "academic_level": "Bachelor", "duration_years": 5},
    ],
}

ROOMS = [
    {"name": "Lecture Hall 101", "code": "LH101", "capacity": 120, "room_type": "lecture", "building": "Main Block", "floor": 1, "has_projector": True},
    {"name": "Lecture Hall 102", "code": "LH102", "capacity": 80, "room_type": "lecture", "building": "Main Block", "floor": 1, "has_projector": True},
    {"name": "Lecture Hall 201", "code": "LH201", "capacity": 60, "room_type": "lecture", "building": "Main Block", "floor": 2, "has_projector": True},
    {"name": "Lecture Hall 301", "code": "LH301", "capacity": 150, "room_type": "lecture", "building": "Annex Block", "floor": 3, "has_projector": True},
    {"name": "Computer Lab A", "code": "LABA", "capacity": 40, "room_type": "lab", "building": "Tech Block", "floor": 1, "has_projector": True, "has_lab_equipment": True},
    {"name": "Computer Lab B", "code": "LABB", "capacity": 40, "room_type": "lab", "building": "Tech Block", "floor": 1, "has_projector": True, "has_lab_equipment": True},
    {"name": "Science Laboratory", "code": "LABS", "capacity": 30, "room_type": "lab", "building": "Science Block", "floor": 1, "has_lab_equipment": True},
    {"name": "Seminar Room 1", "code": "SEM1", "capacity": 25, "room_type": "seminar", "building": "Main Block", "floor": 2, "has_projector": True},
    {"name": "Seminar Room 2", "code": "SEM2", "capacity": 20, "room_type": "seminar", "building": "Main Block", "floor": 3, "has_projector": True},
    {"name": "Auditorium", "code": "AUD", "capacity": 300, "room_type": "lecture", "building": "Main Block", "floor": 0, "has_projector": True},
]

LECTURERS_TEMPLATE = [
    {"name": "Dr. Jane Smith", "email": "j.smith@demo.shedulex.ac", "staff_id": "LECT001", "specialization": "Software Engineering", "max_hours_per_week": 16},
    {"name": "Dr. John Doe", "email": "j.doe@demo.shedulex.ac", "staff_id": "LECT002", "specialization": "Mathematics", "max_hours_per_week": 18},
    {"name": "Prof. Alice Johnson", "email": "a.johnson@demo.shedulex.ac", "staff_id": "LECT003", "specialization": "Information Systems", "max_hours_per_week": 14},
    {"name": "Dr. Bob Wilson", "email": "b.wilson@demo.shedulex.ac", "staff_id": "LECT004", "specialization": "Database Systems", "max_hours_per_week": 16},
    {"name": "Dr. Carol Lee", "email": "c.lee@demo.shedulex.ac", "staff_id": "LECT005", "specialization": "Programming Languages", "max_hours_per_week": 18},
    {"name": "Dr. David Kim", "email": "d.kim@demo.shedulex.ac", "staff_id": "LECT006", "specialization": "Computer Networks", "max_hours_per_week": 16},
    {"name": "Prof. Emma Brown", "email": "e.brown@demo.shedulex.ac", "staff_id": "LECT007", "specialization": "Business Management", "max_hours_per_week": 14},
    {"name": "Dr. Frank Torres", "email": "f.torres@demo.shedulex.ac", "staff_id": "LECT008", "specialization": "Electrical Engineering", "max_hours_per_week": 20},
    {"name": "Dr. Grace Patel", "email": "g.patel@demo.shedulex.ac", "staff_id": "LECT009", "specialization": "Statistics and Data Science", "max_hours_per_week": 16},
    {"name": "Dr. Henry Omondi", "email": "h.omondi@demo.shedulex.ac", "staff_id": "LECT010", "specialization": "Artificial Intelligence", "max_hours_per_week": 16},
    {"name": "Dr. Isabella Wanjiru", "email": "i.wanjiru@demo.shedulex.ac", "staff_id": "LECT011", "specialization": "Web Technologies", "max_hours_per_week": 18},
    {"name": "Dr. James Kamau", "email": "j.kamau@demo.shedulex.ac", "staff_id": "LECT012", "specialization": "Cybersecurity", "max_hours_per_week": 16},
    {"name": "Prof. Kevin Mwangi", "email": "k.mwangi@demo.shedulex.ac", "staff_id": "LECT013", "specialization": "Computer Architecture", "max_hours_per_week": 14},
    {"name": "Dr. Linda Otieno", "email": "l.otieno@demo.shedulex.ac", "staff_id": "LECT014", "specialization": "Operating Systems", "max_hours_per_week": 18},
    {"name": "Dr. Michael Njoroge", "email": "m.njoroge@demo.shedulex.ac", "staff_id": "LECT015", "specialization": "Algorithm Design", "max_hours_per_week": 16},
]

# Courses per program: (name, code, semester, year_of_study, requires_lab, course_type)
COURSES_PER_PROGRAM = {
    "BCS": [
        ("Introduction to Computing", "BCS101", 1, 1, False, "core"),
        ("Programming I (Python)", "BCS102", 1, 1, True, "core"),
        ("Discrete Mathematics", "BCS103", 1, 1, False, "core"),
        ("Digital Logic Design", "BCS104", 2, 1, True, "core"),
        ("Data Structures and Algorithms", "BCS201", 1, 2, False, "core"),
        ("Database Systems", "BCS202", 1, 2, True, "core"),
        ("Operating Systems", "BCS203", 2, 2, False, "core"),
        ("Computer Networks", "BCS204", 2, 2, False, "core"),
        ("Software Engineering", "BCS301", 1, 3, False, "core"),
        ("Artificial Intelligence", "BCS302", 1, 3, False, "core"),
        ("Mobile App Development", "BCS303", 2, 3, True, "elective"),
        ("Final Year Project", "BCS401", 1, 4, True, "core"),
    ],
    "BIT": [
        ("IT Fundamentals", "BIT101", 1, 1, True, "core"),
        ("Web Technologies", "BIT102", 1, 1, True, "core"),
        ("Business Communication", "BIT103", 1, 1, False, "core"),
        ("Systems Analysis and Design", "BIT201", 1, 2, False, "core"),
        ("E-Commerce Systems", "BIT202", 2, 2, True, "core"),
        ("Project Management", "BIT203", 2, 2, False, "core"),
        ("Cloud Computing", "BIT301", 1, 3, True, "elective"),
        ("IT Security", "BIT302", 2, 3, False, "core"),
    ],
    "DCS": [
        ("Computer Fundamentals", "DCS101", 1, 1, True, "core"),
        ("Introduction to Programming", "DCS102", 1, 1, True, "core"),
        ("Computer Hardware", "DCS103", 2, 1, True, "core"),
        ("Office Applications", "DCS104", 2, 1, True, "core"),
    ],
    "BCom": [
        ("Business Mathematics", "BCom101", 1, 1, False, "core"),
        ("Principles of Economics", "BCom102", 1, 1, False, "core"),
        ("Financial Accounting", "BCom201", 1, 2, False, "core"),
        ("Marketing Management", "BCom202", 2, 2, False, "core"),
    ],
    "BBA": [
        ("Organizational Behaviour", "BBA101", 1, 1, False, "core"),
        ("Business Statistics", "BBA102", 1, 1, False, "core"),
        ("Strategic Management", "BBA201", 2, 2, False, "core"),
    ],
    "BSMath": [
        ("Calculus I", "MATH101", 1, 1, False, "core"),
        ("Linear Algebra", "MATH102", 1, 1, False, "core"),
        ("Probability and Statistics", "MATH201", 1, 2, False, "core"),
        ("Numerical Analysis", "MATH202", 2, 2, False, "core"),
    ],
    "DDS": [
        ("Introduction to Data Science", "DDS101", 1, 1, True, "core"),
        ("Python for Data Analysis", "DDS102", 1, 1, True, "core"),
        ("Machine Learning Basics", "DDS201", 1, 2, True, "core"),
    ],
    "BSCS": [
        ("Computer Programming", "BSCS101", 1, 1, True, "core"),
        ("Data Structures", "BSCS102", 2, 1, False, "core"),
        ("Database Management", "BSCS201", 1, 2, True, "core"),
        ("Software Design", "BSCS202", 2, 2, False, "core"),
        ("Distributed Systems", "BSCS301", 1, 3, False, "core"),
    ],
    "BIS": [
        ("Information Management", "BIS101", 1, 1, False, "core"),
        ("Library & Information Science", "BIS102", 2, 1, False, "core"),
        ("Digital Preservation", "BIS201", 1, 2, False, "core"),
    ],
    "CIT": [
        ("Computer Basics", "CIT101", 1, 1, True, "core"),
        ("Office Productivity", "CIT102", 2, 1, True, "core"),
        ("Internet and Web Basics", "CIT103", 2, 1, True, "core"),
    ],
    "BBM": [
        ("Foundations of Management", "BBM101", 1, 1, False, "core"),
        ("Entrepreneurship", "BBM102", 2, 1, False, "core"),
        ("Operations Management", "BBM201", 1, 2, False, "core"),
    ],
    "DBA": [
        ("Business Administration Basics", "DBA101", 1, 1, False, "core"),
        ("Accounting Principles", "DBA102", 2, 1, False, "core"),
    ],
    "BEE": [
        ("Circuit Theory", "EEE101", 1, 1, True, "core"),
        ("Digital Electronics", "EEE102", 2, 1, True, "core"),
        ("Signals and Systems", "EEE201", 1, 2, False, "core"),
        ("Power Systems", "EEE202", 2, 2, True, "core"),
    ],
    "BCE": [
        ("Engineering Mathematics", "CEE101", 1, 1, False, "core"),
        ("Structural Analysis", "CEE102", 2, 1, True, "core"),
        ("Fluid Mechanics", "CEE201", 1, 2, True, "core"),
    ],
}

# Which lecturers (by index) teach which programs (by code)
LECTURER_PROGRAM_MAP = {
    "BCS": [0, 3, 4, 9, 12],   # Jane Smith, Bob Wilson, Carol Lee, Henry Omondi, Kevin Mwangi
    "BIT": [2, 10, 5, 11],      # Alice Johnson, Isabella Wanjiru, David Kim, James Kamau
    "DCS": [0, 4, 14],          # Jane Smith, Carol Lee, Michael Njoroge
    "BCom": [6, 1],             # Emma Brown, John Doe
    "BBA": [6],
    "BSMath": [1, 8],           # John Doe, Grace Patel
    "DDS": [8, 9],              # Grace Patel, Henry Omondi
    "BSCS": [0, 3, 14, 9],     # Jane, Bob, Michael, Henry
    "BIS": [2, 13],             # Alice Johnson, Linda Otieno
    "CIT": [10, 0],             # Isabella, Jane
    "BBM": [6],                 # Emma Brown
    "DBA": [6, 8],
    "BEE": [7],                 # Frank Torres
    "BCE": [7, 1],              # Frank Torres, John Doe
}

# Which lecturer (by index) is primary for each course code prefix
COURSE_LECTURER_MAP = {
    "BCS": 0, "BIT": 2, "DCS": 4, "BCom": 6, "BBA": 6,
    "BSMath": 1, "DDS": 8, "BSCS": 14, "BIS": 2, "CIT": 10,
    "BBM": 6, "DBA": 6, "EEE": 7, "CEE": 7, "MATH": 1,
}


def get_or_create(model, lookup_fields, **extra):
    """Return existing instance or create new one. Flushes to get PK."""
    instance = model.query.filter_by(**lookup_fields).first()
    if instance:
        return instance, False
    instance = model(**{**lookup_fields, **extra})
    db.session.add(instance)
    db.session.flush()  # Assign PK (uuid default fires on INSERT)
    return instance, True


def seed():
    app = create_app("production")
    with app.app_context():
        print("\n=== Shedulex Demo Data Seeder ===\n")
        counts = {"universities": 0, "departments": 0, "programs": 0, "student_groups": 0,
                  "rooms": 0, "lecturers": 0, "courses": 0}

        # ── Rooms ─────────────────────────────────────────────────────────────
        print("Creating rooms...")
        for r in ROOMS:
            _, created = get_or_create(Room, {"code": r["code"]}, **{k: v for k, v in r.items() if k != "code"})
            if created:
                counts["rooms"] += 1
        db.session.commit()

        # ── Universities ──────────────────────────────────────────────────────
        print("Creating universities...")
        uni_map = {}  # code → University
        for u in UNIVERSITIES:
            uni, created = get_or_create(University, {"code": u["code"]}, **{k: v for k, v in u.items() if k != "code"})
            uni_map[u["code"]] = uni
            if created:
                counts["universities"] += 1
        db.session.commit()

        # ── Departments ───────────────────────────────────────────────────────
        print("Creating departments...")
        dept_map = {}  # dept_code → Department
        for uni_code, depts in DEPARTMENTS.items():
            uni = uni_map[uni_code]
            for d in depts:
                dept, created = get_or_create(
                    Department,
                    {"code": d["code"], "university_id": uni.id},
                    name=d["name"], faculty=d["faculty"], head_name=d["head_name"],
                )
                dept_map[d["code"]] = dept
                if created:
                    counts["departments"] += 1
        db.session.commit()

        # ── Lecturers ─────────────────────────────────────────────────────────
        print("Creating lecturers...")
        lecturers = []
        # Assign lecturers to departments: first half to FIT, rest distributed
        dept_codes_cycle = ["FIT", "FAS", "FoCom", "SCI", "SoB", "SOE"]
        for i, ldata in enumerate(LECTURERS_TEMPLATE):
            dept_code = dept_codes_cycle[i % len(dept_codes_cycle)]
            dept = dept_map.get(dept_code)
            lect, created = get_or_create(
                Lecturer,
                {"email": ldata["email"]},
                name=ldata["name"],
                staff_id=ldata["staff_id"],
                specialization=ldata["specialization"],
                max_hours_per_week=ldata["max_hours_per_week"],
                department_id=dept.id if dept else None,
            )
            lecturers.append(lect)
            if created:
                counts["lecturers"] += 1
        db.session.commit()

        # ── Programs & student groups ─────────────────────────────────────────
        print("Creating programs and student groups...")
        program_map = {}  # prog_code → Program
        for dept_code, prog_list in PROGRAMS.items():
            dept = dept_map.get(dept_code)
            if not dept:
                continue
            for p in prog_list:
                prog, created = get_or_create(
                    Program,
                    {"code": p["code"], "department_id": dept.id},
                    name=p["name"],
                    academic_level=p["academic_level"],
                    duration_years=p["duration_years"],
                )
                program_map[p["code"]] = prog
                if created:
                    counts["programs"] += 1

                # Assign lecturers to this program
                lect_indices = LECTURER_PROGRAM_MAP.get(p["code"], [])
                for idx in lect_indices:
                    if idx < len(lecturers) and lecturers[idx] not in prog.lecturers:
                        prog.lecturers.append(lecturers[idx])

                # Create student groups for years 1-3 (or duration if shorter)
                max_year = min(p["duration_years"], 3)
                for year in range(1, max_year + 1):
                    for group_letter in ("A", "B"):
                        group_code = f"{p['code']}-Y{year}{group_letter}"
                        group_name = f"{p['code']} Year {year} Group {group_letter}"
                        grp, grp_created = get_or_create(
                            StudentGroup,
                            {"code": group_code, "program_id": prog.id},
                            name=group_name,
                            year_of_study=year,
                            semester=1,
                            student_count=30 + (5 if group_letter == "A" else 0),
                        )
                        if grp_created:
                            counts["student_groups"] += 1

        db.session.commit()

        # ── Courses ───────────────────────────────────────────────────────────
        print("Creating courses...")
        for prog_code, course_list in COURSES_PER_PROGRAM.items():
            prog = program_map.get(prog_code)
            if not prog:
                continue
            # Find default lecturer for this program
            lect_idx = COURSE_LECTURER_MAP.get(prog_code)
            default_lect = lecturers[lect_idx] if lect_idx is not None and lect_idx < len(lecturers) else None

            for name, code, sem, year, req_lab, ctype in course_list:
                # Assign primary lecturer (rotate through program lecturers)
                prog_lect_indices = LECTURER_PROGRAM_MAP.get(prog_code, [])
                course_idx = course_list.index((name, code, sem, year, req_lab, ctype))
                lect_for_course = None
                if prog_lect_indices:
                    lect_for_course = lecturers[prog_lect_indices[course_idx % len(prog_lect_indices)]]

                course, created = get_or_create(
                    Course,
                    {"code": code},
                    name=name,
                    department_id=prog.department_id,
                    program_id=prog.id,
                    lecturer_id=lect_for_course.id if lect_for_course else None,
                    semester=sem,
                    year_of_study=year,
                    credit_hours=3,
                    weekly_hours=3,
                    student_count=35,
                    requires_lab=req_lab,
                    course_type=ctype,
                )
                if created:
                    counts["courses"] += 1

        db.session.commit()

        # ── Summary ───────────────────────────────────────────────────────────
        print("\n=== Seeding complete ===")
        for entity, count in counts.items():
            total = {
                "universities": University.query.count(),
                "departments": Department.query.count(),
                "programs": Program.query.count(),
                "student_groups": StudentGroup.query.count(),
                "rooms": Room.query.count(),
                "lecturers": Lecturer.query.count(),
                "courses": Course.query.count(),
            }[entity]
            status = f"(+{count} new)" if count else "(already existed)"
            print(f"  {entity:20s}: {total:4d} total  {status}")

        print("\nTip: Go to the Generate view to create a timetable for any department.\n")


if __name__ == "__main__":
    seed()
