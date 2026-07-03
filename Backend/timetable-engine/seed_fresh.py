#!/usr/bin/env python3
"""
Fresh start seeder — wipes ALL timetable-engine data then seeds 5 universities
with complete resources: rooms, time templates, academic years, departments,
lecturers, programs, student groups, courses, and course-group assignments.

Run:  docker compose exec timetable-engine python seed_fresh.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import text
from app import create_app
from app.extensions import db
from app.models.domain import (
    AcademicYear, Constraint, Course, Department, Lecturer, Program,
    Room, StudentGroup, TemplateTimeBlock, TimeSlot, Timetable,
    TimetableEntry, TimetableTemplate, University,
)

# ── Deterministic UUIDs (shared with seed_users.py in auth-service) ───────────
UNI_IDS = {
    "STR": "a0000001-0000-0000-0000-000000000001",
    "UON": "a0000001-0000-0000-0000-000000000002",
    "KU":  "a0000001-0000-0000-0000-000000000003",
    "MU":  "a0000001-0000-0000-0000-000000000004",
    "TUK": "a0000001-0000-0000-0000-000000000005",
}

# ── University definitions ─────────────────────────────────────────────────────
UNIVERSITIES = [
    {"id": UNI_IDS["STR"], "name": "Strathmore University",                    "code": "STR", "address": "Ole Sangale Road, Nairobi", "website": "https://strathmore.edu"},
    {"id": UNI_IDS["UON"], "name": "University of Nairobi",                    "code": "UON", "address": "Harry Thuku Road, Nairobi", "website": "https://uonbi.ac.ke"},
    {"id": UNI_IDS["KU"],  "name": "Kenyatta University",                      "code": "KU",  "address": "Thika Road, Nairobi",       "website": "https://ku.ac.ke"},
    {"id": UNI_IDS["MU"],  "name": "Moi University",                           "code": "MU",  "address": "Eldoret, Rift Valley",      "website": "https://mu.ac.ke"},
    {"id": UNI_IDS["TUK"], "name": "Technical University of Kenya",            "code": "TUK", "address": "Haile Selassie Ave, Nairobi","website": "https://tukenya.ac.ke"},
]

# ── Departments (per university code) ─────────────────────────────────────────
DEPARTMENTS = {
    "STR": [
        {"name": "Faculty of Information Technology", "code": "STR-FIT", "faculty": "Science & Technology", "head_name": "Prof. Sarah Wanjiku"},
        {"name": "Faculty of Commerce",               "code": "STR-FoC", "faculty": "Business",             "head_name": "Dr. Peter Kamau"},
    ],
    "UON": [
        {"name": "School of Computing & Informatics", "code": "UON-SCI", "faculty": "Computing",   "head_name": "Prof. James Otieno"},
        {"name": "School of Business",                "code": "UON-SoB", "faculty": "Business",    "head_name": "Dr. Alice Ndungu"},
    ],
    "KU": [
        {"name": "Department of Computer Science",    "code": "KU-DCS",  "faculty": "Pure & Applied Sciences", "head_name": "Prof. Esther Wangari"},
        {"name": "Department of Mathematics",         "code": "KU-DM",   "faculty": "Pure & Applied Sciences", "head_name": "Dr. Samuel Kariuki"},
    ],
    "MU": [
        {"name": "School of Engineering",             "code": "MU-SoE",  "faculty": "Engineering",  "head_name": "Prof. Daniel Rotich"},
        {"name": "School of Sciences",                "code": "MU-SoS",  "faculty": "Sciences",     "head_name": "Dr. Florence Chepkemoi"},
    ],
    "TUK": [
        {"name": "Department of Electrical Engineering",  "code": "TUK-DEE", "faculty": "Engineering", "head_name": "Prof. John Mugo"},
        {"name": "Department of Mechanical Engineering",  "code": "TUK-DME", "faculty": "Engineering", "head_name": "Dr. Lucy Nyambura"},
    ],
}

# ── Programs (indexed by department code) ─────────────────────────────────────
PROGRAMS = {
    "STR-FIT": [
        {"name": "Bachelor of Science in Computer Science", "code": "STR-BCS", "level": "Bachelor", "years": 4},
        {"name": "Bachelor of Information Technology",      "code": "STR-BIT", "level": "Bachelor", "years": 4},
        {"name": "Diploma in Computer Science",             "code": "STR-DCS", "level": "Diploma",  "years": 2},
    ],
    "STR-FoC": [
        {"name": "Bachelor of Commerce",              "code": "STR-BCom", "level": "Bachelor", "years": 4},
        {"name": "Bachelor of Business Administration","code": "STR-BBA", "level": "Bachelor", "years": 4},
    ],
    "UON-SCI": [
        {"name": "Bachelor of Science in Computer Science", "code": "UON-BCS", "level": "Bachelor", "years": 4},
        {"name": "Bachelor of Information Science",         "code": "UON-BIS", "level": "Bachelor", "years": 4},
    ],
    "UON-SoB": [
        {"name": "Bachelor of Business Management",  "code": "UON-BBM", "level": "Bachelor", "years": 4},
        {"name": "Diploma in Business Administration","code": "UON-DBA", "level": "Diploma",  "years": 2},
    ],
    "KU-DCS": [
        {"name": "Bachelor of Science in Computer Science", "code": "KU-BCS", "level": "Bachelor", "years": 4},
        {"name": "Certificate in Information Technology",   "code": "KU-CIT", "level": "Certificate","years": 1},
    ],
    "KU-DM": [
        {"name": "Bachelor of Science in Mathematics",      "code": "KU-BSM", "level": "Bachelor", "years": 4},
        {"name": "Diploma in Statistics",                   "code": "KU-DST", "level": "Diploma",  "years": 2},
    ],
    "MU-SoE": [
        {"name": "Bachelor of Science in Electrical Engineering","code": "MU-BEE","level": "Bachelor","years": 5},
        {"name": "Bachelor of Science in Civil Engineering",     "code": "MU-BCE","level": "Bachelor","years": 5},
    ],
    "MU-SoS": [
        {"name": "Bachelor of Science in Physics",   "code": "MU-BSP", "level": "Bachelor", "years": 4},
        {"name": "Bachelor of Science in Chemistry", "code": "MU-BSC", "level": "Bachelor", "years": 4},
    ],
    "TUK-DEE": [
        {"name": "Bachelor of Technology in Electrical Engineering","code": "TUK-BTE","level": "Bachelor","years": 4},
        {"name": "Diploma in Electrical Engineering",               "code": "TUK-DEE2","level": "Diploma","years": 3},
    ],
    "TUK-DME": [
        {"name": "Bachelor of Technology in Mechanical Engineering","code": "TUK-BTM","level": "Bachelor","years": 4},
        {"name": "Diploma in Automotive Engineering",               "code": "TUK-DAE","level": "Diploma","years": 3},
    ],
}

# ── Rooms (per university, with university_id key inserted at runtime) ─────────
ROOM_TEMPLATES = [
    {"name": "Lecture Hall A",  "code": "LHA",   "capacity": 120, "room_type": "lecture",  "building": "Main Block",  "floor": 1, "has_projector": True},
    {"name": "Lecture Hall B",  "code": "LHB",   "capacity": 80,  "room_type": "lecture",  "building": "Main Block",  "floor": 2, "has_projector": True},
    {"name": "Lecture Hall C",  "code": "LHC",   "capacity": 60,  "room_type": "lecture",  "building": "Annex",       "floor": 1, "has_projector": True},
    {"name": "Computer Lab 1",  "code": "CLAB1", "capacity": 40,  "room_type": "lab",      "building": "Tech Block",  "floor": 1, "has_projector": True,  "has_lab_equipment": True},
    {"name": "Computer Lab 2",  "code": "CLAB2", "capacity": 40,  "room_type": "lab",      "building": "Tech Block",  "floor": 1, "has_projector": True,  "has_lab_equipment": True},
    {"name": "Seminar Room 1",  "code": "SEM1",  "capacity": 25,  "room_type": "seminar",  "building": "Main Block",  "floor": 3, "has_projector": True},
]

# ── Lecturers (per university) — names vary per institution ────────────────────
LECTURERS_PER_UNI = {
    "STR": [
        {"name": "Dr. Jane Smith",        "email": "j.smith@str.ac",     "staff_id": "STR001", "specialization": "Software Engineering",    "max_hours": 16},
        {"name": "Dr. John Doe",          "email": "j.doe@str.ac",       "staff_id": "STR002", "specialization": "Database Systems",         "max_hours": 18},
        {"name": "Prof. Alice Johnson",   "email": "a.johnson@str.ac",   "staff_id": "STR003", "specialization": "Information Systems",      "max_hours": 14},
        {"name": "Dr. Bob Wilson",        "email": "b.wilson@str.ac",    "staff_id": "STR004", "specialization": "Business Management",      "max_hours": 16},
        {"name": "Dr. Carol Lee",         "email": "c.lee@str.ac",       "staff_id": "STR005", "specialization": "Marketing & E-Commerce",   "max_hours": 18},
        {"name": "Dr. David Kim",         "email": "d.kim@str.ac",       "staff_id": "STR006", "specialization": "Computer Networks",        "max_hours": 16},
    ],
    "UON": [
        {"name": "Prof. James Otieno",    "email": "j.otieno@uon.ac",    "staff_id": "UON001", "specialization": "Artificial Intelligence",  "max_hours": 14},
        {"name": "Dr. Grace Mwangi",      "email": "g.mwangi@uon.ac",   "staff_id": "UON002", "specialization": "Web Technologies",         "max_hours": 18},
        {"name": "Dr. Peter Kamau",       "email": "p.kamau@uon.ac",     "staff_id": "UON003", "specialization": "Business Analytics",       "max_hours": 16},
        {"name": "Prof. Emma Ndungu",     "email": "e.ndungu@uon.ac",    "staff_id": "UON004", "specialization": "Strategic Management",     "max_hours": 14},
        {"name": "Dr. Samuel Ochieng",    "email": "s.ochieng@uon.ac",   "staff_id": "UON005", "specialization": "Data Science",             "max_hours": 16},
        {"name": "Dr. Ruth Wanjiru",      "email": "r.wanjiru@uon.ac",   "staff_id": "UON006", "specialization": "Information Management",   "max_hours": 18},
    ],
    "KU": [
        {"name": "Prof. Esther Wangari",  "email": "e.wangari@ku.ac",   "staff_id": "KU001",  "specialization": "Algorithms",              "max_hours": 14},
        {"name": "Dr. Samuel Kariuki",    "email": "s.kariuki@ku.ac",    "staff_id": "KU002",  "specialization": "Statistics",              "max_hours": 18},
        {"name": "Dr. Amina Hassan",      "email": "a.hassan@ku.ac",     "staff_id": "KU003",  "specialization": "Operating Systems",       "max_hours": 16},
        {"name": "Prof. Michael Njoroge", "email": "m.njoroge@ku.ac",    "staff_id": "KU004",  "specialization": "Applied Mathematics",     "max_hours": 14},
        {"name": "Dr. Faith Chebet",      "email": "f.chebet@ku.ac",     "staff_id": "KU005",  "specialization": "Calculus & Analysis",     "max_hours": 18},
    ],
    "MU": [
        {"name": "Prof. Daniel Rotich",   "email": "d.rotich@mu.ac",    "staff_id": "MU001",  "specialization": "Electrical Engineering",  "max_hours": 16},
        {"name": "Dr. Florence Chepkemoi","email": "f.chepkemoi@mu.ac", "staff_id": "MU002",  "specialization": "Physical Chemistry",      "max_hours": 18},
        {"name": "Dr. Collins Sang",      "email": "c.sang@mu.ac",      "staff_id": "MU003",  "specialization": "Structural Engineering",  "max_hours": 16},
        {"name": "Prof. Vivian Cheruiyot","email": "v.cheruiyot@mu.ac", "staff_id": "MU004",  "specialization": "Thermodynamics",          "max_hours": 14},
        {"name": "Dr. Felix Mutai",       "email": "f.mutai@mu.ac",     "staff_id": "MU005",  "specialization": "Physics",                 "max_hours": 18},
    ],
    "TUK": [
        {"name": "Prof. John Mugo",       "email": "j.mugo@tuk.ac",      "staff_id": "TUK001", "specialization": "Power Systems",           "max_hours": 16},
        {"name": "Dr. Lucy Nyambura",     "email": "l.nyambura@tuk.ac",  "staff_id": "TUK002", "specialization": "Mechanical Design",       "max_hours": 18},
        {"name": "Dr. Eric Korir",        "email": "e.korir@tuk.ac",     "staff_id": "TUK003", "specialization": "Control Systems",         "max_hours": 16},
        {"name": "Prof. Nancy Wachira",   "email": "n.wachira@tuk.ac",   "staff_id": "TUK004", "specialization": "Fluid Mechanics",         "max_hours": 14},
        {"name": "Dr. Kevin Kimani",      "email": "k.kimani@tuk.ac",    "staff_id": "TUK005", "specialization": "Digital Electronics",     "max_hours": 18},
    ],
}

# ── Courses per program code ───────────────────────────────────────────────────
# (name, code, semester, year, requires_lab, course_type, weekly_hours)
COURSES_MAP = {
    "STR-BCS": [
        ("Introduction to Computing",      "STRBCS101", 1, 1, False, "core",     3),
        ("Programming I",                  "STRBCS102", 1, 1, True,  "core",     4),
        ("Discrete Mathematics",           "STRBCS103", 1, 1, False, "core",     3),
        ("Data Structures & Algorithms",   "STRBCS201", 1, 2, False, "core",     3),
        ("Database Systems",               "STRBCS202", 1, 2, True,  "core",     4),
        ("Operating Systems",              "STRBCS203", 2, 2, False, "core",     3),
        ("Software Engineering",           "STRBCS301", 1, 3, False, "core",     3),
        ("Artificial Intelligence",        "STRBCS302", 2, 3, False, "elective", 3),
    ],
    "STR-BIT": [
        ("IT Fundamentals",                "STRBIT101", 1, 1, True,  "core",     3),
        ("Web Technologies",               "STRBIT102", 1, 1, True,  "core",     4),
        ("Systems Analysis & Design",      "STRBIT201", 1, 2, False, "core",     3),
        ("Cloud Computing",                "STRBIT202", 2, 2, True,  "elective", 3),
        ("IT Security",                    "STRBIT203", 2, 2, False, "core",     3),
    ],
    "STR-DCS": [
        ("Computer Fundamentals",          "STRDCS101", 1, 1, True,  "core",     3),
        ("Introduction to Programming",    "STRDCS102", 1, 1, True,  "core",     4),
        ("Office Applications",            "STRDCS103", 2, 1, True,  "core",     3),
    ],
    "STR-BCom": [
        ("Business Mathematics",           "STRBCO101", 1, 1, False, "core",     3),
        ("Principles of Economics",        "STRBCO102", 1, 1, False, "core",     3),
        ("Financial Accounting",           "STRBCO201", 1, 2, False, "core",     3),
        ("Marketing Management",           "STRBCO202", 2, 2, False, "core",     3),
    ],
    "STR-BBA": [
        ("Organisational Behaviour",       "STRBBA101", 1, 1, False, "core",     3),
        ("Business Statistics",            "STRBBA102", 1, 1, False, "core",     3),
        ("Strategic Management",           "STRBBA201", 2, 2, False, "core",     3),
    ],
    "UON-BCS": [
        ("Computer Programming",           "UONBCS101", 1, 1, True,  "core",     4),
        ("Data Structures",                "UONBCS102", 2, 1, False, "core",     3),
        ("Database Management",            "UONBCS201", 1, 2, True,  "core",     4),
        ("Software Design",                "UONBCS202", 2, 2, False, "core",     3),
        ("Distributed Systems",            "UONBCS301", 1, 3, False, "core",     3),
    ],
    "UON-BIS": [
        ("Information Management",         "UONBIS101", 1, 1, False, "core",     3),
        ("Library & Information Science",  "UONBIS102", 2, 1, False, "core",     3),
        ("Digital Preservation",           "UONBIS201", 1, 2, False, "core",     3),
    ],
    "UON-BBM": [
        ("Foundations of Management",      "UONBBM101", 1, 1, False, "core",     3),
        ("Entrepreneurship",               "UONBBM102", 2, 1, False, "core",     3),
        ("Operations Management",          "UONBBM201", 1, 2, False, "core",     3),
    ],
    "UON-DBA": [
        ("Business Admin Basics",          "UONDBA101", 1, 1, False, "core",     3),
        ("Accounting Principles",          "UONDBA102", 2, 1, False, "core",     3),
    ],
    "KU-BCS": [
        ("Programming Fundamentals",       "KUBCS101",  1, 1, True,  "core",     4),
        ("Discrete Structures",            "KUBCS102",  1, 1, False, "core",     3),
        ("Data Structures",                "KUBCS201",  1, 2, False, "core",     3),
        ("Algorithm Design",               "KUBCS202",  2, 2, False, "core",     3),
        ("Machine Learning",               "KUBCS301",  1, 3, True,  "elective", 3),
    ],
    "KU-CIT": [
        ("Computer Basics",                "KUCIT101",  1, 1, True,  "core",     3),
        ("Office Productivity",            "KUCIT102",  2, 1, True,  "core",     3),
    ],
    "KU-BSM": [
        ("Calculus I",                     "KUBSM101",  1, 1, False, "core",     4),
        ("Linear Algebra",                 "KUBSM102",  1, 1, False, "core",     3),
        ("Probability & Statistics",       "KUBSM201",  1, 2, False, "core",     3),
        ("Numerical Analysis",             "KUBSM202",  2, 2, False, "core",     3),
    ],
    "KU-DST": [
        ("Intro to Statistics",            "KUDST101",  1, 1, False, "core",     3),
        ("Applied Statistics",             "KUDST102",  2, 1, False, "core",     3),
    ],
    "MU-BEE": [
        ("Circuit Theory",                 "MUBEE101",  1, 1, True,  "core",     4),
        ("Digital Electronics",            "MUBEE102",  2, 1, True,  "core",     4),
        ("Signals & Systems",              "MUBEE201",  1, 2, False, "core",     3),
        ("Power Systems",                  "MUBEE202",  2, 2, True,  "core",     4),
    ],
    "MU-BCE": [
        ("Engineering Mathematics",        "MUBCE101",  1, 1, False, "core",     4),
        ("Structural Analysis",            "MUBCE102",  2, 1, True,  "core",     4),
        ("Fluid Mechanics",                "MUBCE201",  1, 2, True,  "core",     4),
    ],
    "MU-BSP": [
        ("Classical Mechanics",            "MUBSP101",  1, 1, False, "core",     3),
        ("Electromagnetism",               "MUBSP102",  2, 1, True,  "core",     3),
        ("Thermodynamics",                 "MUBSP201",  1, 2, False, "core",     3),
    ],
    "MU-BSC": [
        ("General Chemistry",              "MUBSC101",  1, 1, True,  "core",     3),
        ("Organic Chemistry",              "MUBSC102",  2, 1, True,  "core",     3),
        ("Physical Chemistry",             "MUBSC201",  1, 2, True,  "core",     3),
    ],
    "TUK-BTE": [
        ("Fundamentals of Electrical Eng", "TUKBTE101", 1, 1, True,  "core",     4),
        ("Circuit Analysis",               "TUKBTE102", 2, 1, True,  "core",     4),
        ("Control Systems",                "TUKBTE201", 1, 2, False, "core",     3),
        ("Power Electronics",              "TUKBTE202", 2, 2, True,  "core",     4),
    ],
    "TUK-DEE2": [
        ("Electrical Installation",        "TUKDEE101", 1, 1, True,  "core",     4),
        ("Electronics Basics",             "TUKDEE102", 2, 1, True,  "core",     4),
        ("Industrial Automation",          "TUKDEE201", 1, 2, True,  "core",     3),
    ],
    "TUK-BTM": [
        ("Engineering Drawing",            "TUKBTM101", 1, 1, True,  "core",     3),
        ("Mechanics of Materials",         "TUKBTM102", 2, 1, False, "core",     3),
        ("Thermodynamics",                 "TUKBTM201", 1, 2, False, "core",     3),
        ("Manufacturing Processes",        "TUKBTM202", 2, 2, True,  "core",     4),
    ],
    "TUK-DAE": [
        ("Automotive Technology",          "TUKDAE101", 1, 1, True,  "core",     4),
        ("Vehicle Systems",                "TUKDAE102", 2, 1, True,  "core",     4),
    ],
}

# ── Time block template (Mon-Fri, 7 class periods + breaks) ───────────────────
TIME_BLOCKS = [
    {"label": "Period 1",  "start": "08:00", "end": "09:00", "type": "class"},
    {"label": "Period 2",  "start": "09:00", "end": "10:00", "type": "class"},
    {"label": "Break",     "start": "10:00", "end": "10:30", "type": "break"},
    {"label": "Period 3",  "start": "10:30", "end": "11:30", "type": "class"},
    {"label": "Period 4",  "start": "11:30", "end": "12:30", "type": "class"},
    {"label": "Lunch",     "start": "12:30", "end": "13:30", "type": "lunch"},
    {"label": "Period 5",  "start": "13:30", "end": "14:30", "type": "class"},
    {"label": "Period 6",  "start": "14:30", "end": "15:30", "type": "class"},
    {"label": "Period 7",  "start": "15:30", "end": "16:30", "type": "class"},
]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


# ── Helpers ───────────────────────────────────────────────────────────────────
def wipe_all(session):
    """Delete all data in proper dependency order."""
    print("  Wiping existing data…")
    session.execute(text("DELETE FROM timetable_entries"))
    session.execute(text("DELETE FROM timetable_snapshots"))
    session.execute(text("DELETE FROM timetables"))
    session.execute(text("DELETE FROM course_student_groups"))
    session.execute(text("DELETE FROM lecturer_programs"))
    session.execute(text("DELETE FROM courses"))
    session.execute(text("DELETE FROM student_groups"))
    session.execute(text("DELETE FROM programs"))
    session.execute(text("DELETE FROM lecturers"))
    session.execute(text("DELETE FROM time_slots"))
    session.execute(text("DELETE FROM template_time_blocks"))
    session.execute(text("DELETE FROM timetable_templates"))
    session.execute(text("DELETE FROM rooms"))
    session.execute(text("DELETE FROM academic_years"))
    session.execute(text("DELETE FROM constraints"))
    session.execute(text("DELETE FROM departments"))
    session.execute(text("DELETE FROM universities"))
    session.commit()
    print("  Done.")


def seed():
    app = create_app("production")
    with app.app_context():
        print("\n=== Shedulex Fresh Seed (5 Universities) ===\n")

        wipe_all(db.session)

        uni_objects   = {}   # code → University
        dept_objects  = {}   # dept_code → Department
        prog_objects  = {}   # prog_code → Program
        lect_objects  = {}   # uni_code → [Lecturer]

        # ── Universities ────────────────────────────────────────────────────
        print("Creating universities…")
        for u in UNIVERSITIES:
            uni = University(
                id=u["id"], name=u["name"], code=u["code"],
                address=u["address"], website=u["website"], is_active=True,
            )
            db.session.add(uni)
            uni_objects[u["code"]] = uni
        db.session.flush()

        # ── Academic Years ───────────────────────────────────────────────────
        print("Creating academic years…")
        for code, uni in uni_objects.items():
            db.session.add(AcademicYear(
                name="2025-2026",
                university_id=uni.id,
                is_current=True,
                status="active",
            ))
        db.session.flush()

        # ── Time templates + time slots ──────────────────────────────────────
        print("Creating time templates and slots…")
        for code, uni in uni_objects.items():
            tmpl = TimetableTemplate(
                name=f"{code} Standard Schedule",
                university_id=uni.id,
                is_default=True,
                days_of_week=DAYS,
            )
            db.session.add(tmpl)
            db.session.flush()

            for i, blk in enumerate(TIME_BLOCKS):
                db.session.add(TemplateTimeBlock(
                    template_id=tmpl.id,
                    label=blk["label"],
                    start_time=blk["start"],
                    end_time=blk["end"],
                    block_type=blk["type"],
                    sort_order=i,
                ))
            db.session.flush()

            # Generate actual time slot rows
            idx = 0
            for day in DAYS:
                for blk in TIME_BLOCKS:
                    is_break = blk["type"] in ("break", "lunch")
                    db.session.add(TimeSlot(
                        day=day,
                        start_time=blk["start"],
                        end_time=blk["end"],
                        slot_index=idx,
                        is_break=is_break,
                        slot_type=blk["type"],
                        label=blk["label"],
                        template_id=tmpl.id,
                    ))
                    idx += 1
        db.session.flush()

        # ── Departments ──────────────────────────────────────────────────────
        print("Creating departments…")
        for uni_code, depts in DEPARTMENTS.items():
            uni = uni_objects[uni_code]
            for d in depts:
                dept = Department(
                    name=d["name"], code=d["code"],
                    faculty=d["faculty"], head_name=d["head_name"],
                    university_id=uni.id,
                )
                db.session.add(dept)
                db.session.flush()
                dept_objects[d["code"]] = dept
        db.session.flush()

        # ── Rooms (per university) ───────────────────────────────────────────
        print("Creating rooms…")
        for uni_code, uni in uni_objects.items():
            for r in ROOM_TEMPLATES:
                room = Room(
                    name=f"{uni_code} {r['name']}",
                    code=f"{uni_code}-{r['code']}",
                    capacity=r["capacity"],
                    room_type=r["room_type"],
                    building=r["building"],
                    floor=r["floor"],
                    has_projector=r.get("has_projector", False),
                    has_lab_equipment=r.get("has_lab_equipment", False),
                    university_id=uni.id,
                )
                db.session.add(room)
        db.session.flush()

        # ── Lecturers ────────────────────────────────────────────────────────
        print("Creating lecturers…")
        lect_phone_counter = 800
        for uni_code, lects in LECTURERS_PER_UNI.items():
            # Assign to first department of this university
            first_dept = next(
                (dept_objects[d["code"]] for d in DEPARTMENTS[uni_code]),
                None
            )
            uni_lects = []
            for l in lects:
                lect = Lecturer(
                    name=l["name"],
                    email=l["email"],
                    phone=l.get("phone") or f"+255700000{lect_phone_counter:03d}",
                    staff_id=l["staff_id"],
                    specialization=l["specialization"],
                    max_hours_per_week=l["max_hours"],
                    department_id=first_dept.id if first_dept else None,
                    is_active=True,
                )
                db.session.add(lect)
                db.session.flush()
                lect_phone_counter += 1
                uni_lects.append(lect)
            lect_objects[uni_code] = uni_lects
        db.session.flush()

        # ── Programs + student groups ────────────────────────────────────────
        print("Creating programs and student groups…")
        for dept_code, prog_list in PROGRAMS.items():
            dept = dept_objects.get(dept_code)
            if not dept:
                continue
            uni_code = dept_code.split("-")[0]
            lects = lect_objects.get(uni_code, [])

            for pi, p in enumerate(prog_list):
                prog = Program(
                    name=p["name"],
                    code=p["code"],
                    department_id=dept.id,
                    academic_level=p["level"],
                    duration_years=p["years"],
                    is_active=True,
                )
                db.session.add(prog)
                db.session.flush()
                prog_objects[p["code"]] = prog

                # Assign lecturers to this program (rotate)
                for li, lect in enumerate(lects):
                    if li % 2 == pi % 2:
                        prog.lecturers.append(lect)

                # Student groups: Year 1 & 2, Groups A & B
                max_year = min(p["years"], 2)
                for year in range(1, max_year + 1):
                    for letter in ("A", "B"):
                        grp_code = f"{p['code']}-Y{year}{letter}"
                        db.session.add(StudentGroup(
                            name=f"{p['code']} Year {year} Group {letter}",
                            code=grp_code,
                            program_id=prog.id,
                            year_of_study=year,
                            semester=1,
                            student_count=32 if letter == "A" else 28,
                            is_active=True,
                        ))
        db.session.flush()

        # ── Courses + assignments ────────────────────────────────────────────
        print("Creating courses and student group assignments…")
        for prog_code, course_list in COURSES_MAP.items():
            prog = prog_objects.get(prog_code)
            if not prog:
                continue
            uni_code = prog_code.split("-")[0]
            lects = lect_objects.get(uni_code, [])

            # Get student groups for this program (Year 1)
            y1_groups = [
                g for g in StudentGroup.query.filter_by(
                    program_id=prog.id, year_of_study=1
                ).all()
            ]
            y2_groups = [
                g for g in StudentGroup.query.filter_by(
                    program_id=prog.id, year_of_study=2
                ).all()
            ]

            for ci, (cname, ccode, sem, year, req_lab, ctype, wh) in enumerate(course_list):
                lect = lects[ci % len(lects)] if lects else None
                course = Course(
                    name=cname,
                    code=ccode,
                    department_id=prog.department_id,
                    program_id=prog.id,
                    lecturer_id=lect.id if lect else None,
                    semester=sem,
                    year_of_study=year,
                    credit_hours=3,
                    weekly_hours=wh,
                    student_count=30,
                    requires_lab=req_lab,
                    course_type=ctype,
                    is_active=True,
                )
                db.session.add(course)
                db.session.flush()

                # Assign student groups
                target_groups = y1_groups if year == 1 else y2_groups
                for g in target_groups:
                    course.student_groups.append(g)

        db.session.commit()

        # ── Summary ──────────────────────────────────────────────────────────
        print("\n=== Seed complete ===")
        print(f"  Universities:   {University.query.count()}")
        print(f"  Departments:    {Department.query.count()}")
        print(f"  Programs:       {Program.query.count()}")
        print(f"  Student groups: {StudentGroup.query.count()}")
        print(f"  Rooms:          {Room.query.count()}")
        print(f"  Lecturers:      {Lecturer.query.count()}")
        print(f"  Courses:        {Course.query.count()}")
        print(f"  Time slots:     {TimeSlot.query.count()}")
        print(f"  Academic years: {AcademicYear.query.count()}")
        print()
        print("University codes and IDs (use these in seed_users.py):")
        for u in University.query.all():
            print(f"  {u.code}: {u.id}")
        print()
        print("Next: run  docker compose exec auth-service python seed_users.py")


if __name__ == "__main__":
    seed()
