#!/usr/bin/env python3
"""
Deletes ONLY Kampala International University's data (scoped strictly to
UNI_ID below) — timetables/entries, courses, student groups, programmes,
lecturers, rooms, buildings, departments, and the university itself. Does
NOT touch any other university's data.

Run BEFORE re-running seed_kiu.py if you want a clean slate:
  docker compose exec timetable-engine python unseed_kiu.py
  docker compose exec timetable-engine python seed_kiu.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import text
from app import create_app
from app.extensions import db

UNI_ID = "b0000001-0000-0000-0000-000000000001"  # must match seed_kiu.py


def unseed():
    app = create_app("production")
    with app.app_context():
        params = {"uni": UNI_ID}

        print("\n=== Deleting Kampala International University data ===\n")

        dept_ids = [r[0] for r in db.session.execute(
            text("SELECT id FROM departments WHERE university_id = :uni"), params
        ).fetchall()]
        prog_ids = [r[0] for r in db.session.execute(
            text("SELECT id FROM programs WHERE department_id = ANY(:depts)"),
            {"depts": dept_ids or [None]},
        ).fetchall()] if dept_ids else []
        course_ids = [r[0] for r in db.session.execute(
            text("SELECT id FROM courses WHERE department_id = ANY(:depts) OR program_id = ANY(:progs)"),
            {"depts": dept_ids or [None], "progs": prog_ids or [None]},
        ).fetchall()] if (dept_ids or prog_ids) else []
        group_ids = [r[0] for r in db.session.execute(
            text("SELECT id FROM student_groups WHERE program_id = ANY(:pids)"),
            {"pids": prog_ids or [None]},
        ).fetchall()] if prog_ids else []
        lecturer_ids = [r[0] for r in db.session.execute(
            text("SELECT id FROM lecturers WHERE department_id = ANY(:depts)"), params | {"depts": dept_ids or [None]}
        ).fetchall()] if dept_ids else []
        room_ids = [r[0] for r in db.session.execute(
            text("SELECT id FROM rooms WHERE university_id = :uni"), params
        ).fetchall()]
        year_ids = [r[0] for r in db.session.execute(
            text("SELECT id FROM academic_years WHERE university_id = :uni"), params
        ).fetchall()]
        timetable_ids = [r[0] for r in db.session.execute(
            text("""
                SELECT id FROM timetables
                WHERE department_id = ANY(:depts) OR program_id = ANY(:progs) OR academic_year_id = ANY(:years)
            """),
            {"depts": dept_ids or [None], "progs": prog_ids or [None], "years": year_ids or [None]},
        ).fetchall()]

        print(f"  Departments: {len(dept_ids)}  Programmes: {len(prog_ids)}  Courses: {len(course_ids)}")
        print(f"  Student groups: {len(group_ids)}  Lecturers: {len(lecturer_ids)}  Rooms: {len(room_ids)}")
        print(f"  Timetables: {len(timetable_ids)}")

        # ── Timetable data first — entries/comments/snapshots reference courses,
        # lecturers, rooms and student groups we're about to delete below.
        db.session.execute(
            text("DELETE FROM timetable_comments WHERE timetable_id = ANY(:tids)"),
            {"tids": timetable_ids or [None]},
        )
        db.session.execute(
            text("""
                DELETE FROM timetable_entries
                WHERE timetable_id = ANY(:tids) OR course_id = ANY(:cids)
                   OR lecturer_id = ANY(:lids) OR room_id = ANY(:rids)
                   OR student_group_id = ANY(:gids)
            """),
            {
                "tids": timetable_ids or [None], "cids": course_ids or [None],
                "lids": lecturer_ids or [None], "rids": room_ids or [None],
                "gids": group_ids or [None],
            },
        )
        db.session.execute(
            text("DELETE FROM timetable_snapshots WHERE timetable_id = ANY(:tids)"),
            {"tids": timetable_ids or [None]},
        )
        db.session.execute(text("DELETE FROM timetables WHERE id = ANY(:tids)"), {"tids": timetable_ids or [None]})

        # ── Department-scoped side tables ────────────────────────────────────
        db.session.execute(
            text("DELETE FROM constraints WHERE department_id = ANY(:depts)"),
            {"depts": dept_ids or [None]},
        )
        db.session.execute(
            text("DELETE FROM lecturer_requests WHERE department_id = ANY(:depts)"),
            {"depts": dept_ids or [None]},
        )

        # ── Core academic data ───────────────────────────────────────────────
        db.session.execute(
            text("DELETE FROM course_student_groups WHERE course_id = ANY(:cids)"),
            {"cids": course_ids or [None]},
        )
        db.session.execute(
            text("DELETE FROM course_group_lecturers WHERE course_id = ANY(:cids)"),
            {"cids": course_ids or [None]},
        )
        db.session.execute(
            text("DELETE FROM lecturer_programs WHERE program_id = ANY(:pids)"),
            {"pids": prog_ids or [None]},
        )
        db.session.execute(text("DELETE FROM courses WHERE id = ANY(:cids)"), {"cids": course_ids or [None]})
        db.session.execute(text("DELETE FROM student_groups WHERE program_id = ANY(:pids)"), {"pids": prog_ids or [None]})
        db.session.execute(text("DELETE FROM programs WHERE id = ANY(:pids)"), {"pids": prog_ids or [None]})
        db.session.execute(text("DELETE FROM lecturers WHERE department_id = ANY(:depts)"), {"depts": dept_ids or [None]})
        db.session.execute(text("DELETE FROM rooms WHERE university_id = :uni"), params)
        db.session.execute(text("DELETE FROM buildings WHERE university_id = :uni"), params)
        db.session.execute(text("DELETE FROM departments WHERE university_id = :uni"), params)
        db.session.execute(text("DELETE FROM academic_years WHERE university_id = :uni"), params)
        db.session.execute(text("DELETE FROM universities WHERE id = :uni"), params)
        db.session.commit()

        print("\n=== Done. Kampala International University fully removed. ===")
        print("Other universities' data was not touched.\n")
        print("Next: docker compose exec timetable-engine python seed_kiu.py")


if __name__ == "__main__":
    unseed()
