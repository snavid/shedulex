#!/usr/bin/env python3
"""
Demo data seeder for the calendar-service database.
Run: docker compose exec calendar-service python seed_demo.py
"""
import sys
import os
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db
from app.models.event import AcademicEvent, AcademicSemester


def seed():
    app = create_app("production")
    with app.app_context():
        print("\n=== Calendar Demo Seeder ===\n")

        # ── Semesters ─────────────────────────────────────────────────────────
        semesters_data = [
            {
                "name": "Semester 1 2025/2026",
                "academic_year": "2025/2026",
                "semester_number": 1,
                "start_date": date(2026, 2, 3),
                "end_date": date(2026, 5, 30),
                "registration_start": date(2026, 1, 15),
                "registration_end": date(2026, 1, 31),
                "exam_start": date(2026, 5, 11),
                "exam_end": date(2026, 5, 30),
                "is_current": True,
            },
            {
                "name": "Semester 2 2025/2026",
                "academic_year": "2025/2026",
                "semester_number": 2,
                "start_date": date(2026, 8, 17),
                "end_date": date(2026, 12, 5),
                "registration_start": date(2026, 8, 1),
                "registration_end": date(2026, 8, 14),
                "exam_start": date(2026, 11, 23),
                "exam_end": date(2026, 12, 5),
                "is_current": False,
            },
        ]

        sem_count = 0
        for s in semesters_data:
            existing = AcademicSemester.query.filter_by(
                academic_year=s["academic_year"],
                semester_number=s["semester_number"],
            ).first()
            if not existing:
                sem = AcademicSemester(**s)
                db.session.add(sem)
                sem_count += 1
        db.session.commit()
        print(f"  Semesters: {AcademicSemester.query.count()} total (+{sem_count} new)")

        # ── Academic Events ───────────────────────────────────────────────────
        events_data = [
            # Semester 1 milestones
            {
                "title": "Semester 1 Registration Opens",
                "event_type": "deadline",
                "start_datetime": datetime(2026, 1, 15, 8, 0, tzinfo=timezone.utc),
                "end_datetime": datetime(2026, 1, 31, 17, 0, tzinfo=timezone.utc),
                "all_day": False,
                "is_public": True,
                "color": "#EAB308",
                "description": "Students must register for courses before the deadline.",
            },
            {
                "title": "Semester 1 Lectures Begin",
                "event_type": "event",
                "start_datetime": datetime(2026, 2, 3, 8, 0, tzinfo=timezone.utc),
                "all_day": True,
                "is_public": True,
                "color": "#10B981",
                "description": "First day of lectures for Semester 1.",
            },
            {
                "title": "Public Holiday – Labour Day",
                "event_type": "holiday",
                "start_datetime": datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc),
                "all_day": True,
                "is_public": True,
                "color": "#EF4444",
                "description": "No classes. Public holiday.",
            },
            {
                "title": "Mid-Semester CAT 1",
                "event_type": "exam",
                "start_datetime": datetime(2026, 3, 16, 8, 0, tzinfo=timezone.utc),
                "end_datetime": datetime(2026, 3, 20, 17, 0, tzinfo=timezone.utc),
                "all_day": False,
                "is_public": True,
                "color": "#F97316",
                "description": "Continuous Assessment Test 1 for all courses.",
            },
            {
                "title": "Mid-Semester CAT 2",
                "event_type": "exam",
                "start_datetime": datetime(2026, 4, 20, 8, 0, tzinfo=timezone.utc),
                "end_datetime": datetime(2026, 4, 24, 17, 0, tzinfo=timezone.utc),
                "all_day": False,
                "is_public": True,
                "color": "#F97316",
                "description": "Continuous Assessment Test 2 for all courses.",
            },
            {
                "title": "Assignment Submission Deadline",
                "event_type": "deadline",
                "start_datetime": datetime(2026, 4, 30, 23, 59, tzinfo=timezone.utc),
                "all_day": False,
                "is_public": True,
                "color": "#EAB308",
                "description": "Final submission deadline for all coursework assignments.",
            },
            {
                "title": "End-of-Semester Examinations",
                "event_type": "exam",
                "start_datetime": datetime(2026, 5, 11, 8, 0, tzinfo=timezone.utc),
                "end_datetime": datetime(2026, 5, 30, 17, 0, tzinfo=timezone.utc),
                "all_day": False,
                "is_public": True,
                "color": "#DC2626",
                "description": "Final examinations for Semester 1. Timetable to be released by the Examinations Office.",
            },
            {
                "title": "Semester Break Begins",
                "event_type": "semester_break",
                "start_datetime": datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc),
                "end_datetime": datetime(2026, 8, 14, 23, 59, tzinfo=timezone.utc),
                "all_day": True,
                "is_public": True,
                "color": "#14B8A6",
                "description": "Inter-semester break. Students may access library and online resources.",
            },
            # Department meetings
            {
                "title": "Faculty Board Meeting – Q1",
                "event_type": "meeting",
                "start_datetime": datetime(2026, 2, 27, 10, 0, tzinfo=timezone.utc),
                "end_datetime": datetime(2026, 2, 27, 13, 0, tzinfo=timezone.utc),
                "all_day": False,
                "location": "Seminar Room 1",
                "is_public": False,
                "color": "#8B5CF6",
                "description": "Quarterly faculty board meeting. Academic staff attendance mandatory.",
            },
            {
                "title": "IT Department HOD Meeting",
                "event_type": "meeting",
                "start_datetime": datetime(2026, 3, 6, 14, 0, tzinfo=timezone.utc),
                "end_datetime": datetime(2026, 3, 6, 16, 0, tzinfo=timezone.utc),
                "all_day": False,
                "location": "Seminar Room 2",
                "is_public": False,
                "color": "#8B5CF6",
            },
            # Student announcements
            {
                "title": "Student Orientation Day",
                "event_type": "event",
                "start_datetime": datetime(2026, 2, 2, 8, 0, tzinfo=timezone.utc),
                "end_datetime": datetime(2026, 2, 2, 17, 0, tzinfo=timezone.utc),
                "all_day": False,
                "location": "Auditorium",
                "is_public": True,
                "color": "#10B981",
                "description": "New student orientation and introduction to campus facilities.",
            },
            {
                "title": "Industry Guest Lecture – Tech Companies",
                "event_type": "event",
                "start_datetime": datetime(2026, 3, 12, 14, 0, tzinfo=timezone.utc),
                "end_datetime": datetime(2026, 3, 12, 17, 0, tzinfo=timezone.utc),
                "location": "Auditorium",
                "all_day": False,
                "is_public": True,
                "color": "#10B981",
                "description": "Representatives from leading tech companies will share career insights.",
            },
            {
                "title": "Annual Sports & Cultural Day",
                "event_type": "event",
                "start_datetime": datetime(2026, 4, 3, 8, 0, tzinfo=timezone.utc),
                "end_datetime": datetime(2026, 4, 3, 18, 0, tzinfo=timezone.utc),
                "all_day": True,
                "is_public": True,
                "color": "#10B981",
                "description": "Annual sports day. No lectures scheduled. All students encouraged to participate.",
            },
            # Announcements
            {
                "title": "Semester 2 Registration Opens",
                "event_type": "deadline",
                "start_datetime": datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc),
                "end_datetime": datetime(2026, 8, 14, 17, 0, tzinfo=timezone.utc),
                "all_day": False,
                "is_public": True,
                "color": "#EAB308",
                "description": "Registration for Semester 2 courses.",
            },
            {
                "title": "Semester 2 Lectures Begin",
                "event_type": "event",
                "start_datetime": datetime(2026, 8, 17, 8, 0, tzinfo=timezone.utc),
                "all_day": True,
                "is_public": True,
                "color": "#10B981",
                "description": "First day of lectures for Semester 2.",
            },
            {
                "title": "Make-up Class – CS201",
                "event_type": "makeup",
                "start_datetime": datetime(2026, 3, 21, 10, 0, tzinfo=timezone.utc),
                "end_datetime": datetime(2026, 3, 21, 12, 0, tzinfo=timezone.utc),
                "location": "LH201",
                "all_day": False,
                "is_public": True,
                "color": "#EC4899",
                "description": "Make-up class for Data Structures (CS201) missed due to lecturer travel.",
            },
            {
                "title": "Graduation Ceremony 2025",
                "event_type": "event",
                "start_datetime": datetime(2026, 6, 27, 9, 0, tzinfo=timezone.utc),
                "end_datetime": datetime(2026, 6, 27, 16, 0, tzinfo=timezone.utc),
                "location": "Auditorium",
                "all_day": False,
                "is_public": True,
                "color": "#10B981",
                "description": "Annual graduation ceremony for the Class of 2025.",
            },
        ]

        evt_count = 0
        for e in events_data:
            existing = AcademicEvent.query.filter_by(
                title=e["title"],
                start_datetime=e["start_datetime"],
            ).first()
            if not existing:
                evt = AcademicEvent(**e)
                db.session.add(evt)
                evt_count += 1
        db.session.commit()
        print(f"  Events:    {AcademicEvent.query.count()} total (+{evt_count} new)")

        print("\n=== Calendar seeding complete ===\n")


if __name__ == "__main__":
    seed()
