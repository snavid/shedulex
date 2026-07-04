import pytest
import uuid


def _seed_base(app):
    from app.extensions import db
    from app.models.domain import (
        University, Department, Program, StudentGroup, Course,
        Lecturer, Room, TimeSlot, Timetable, TimetableEntry,
    )
    from flask_jwt_extended import create_access_token

    suffix = uuid.uuid4().hex[:6]
    with app.app_context():
        uni = University(name=f"Recompute Uni {suffix}", code=f"RC{suffix}")
        db.session.add(uni)
        db.session.flush()
        dept = Department(name=f"CS RC {suffix}", code=f"CS{suffix}", university_id=uni.id)
        db.session.add(dept)
        db.session.flush()
        prog = Program(name=f"BCS RC {suffix}", code=f"BC{suffix}", department_id=dept.id)
        db.session.add(prog)
        db.session.flush()
        group_a = StudentGroup(name="Group A", code="GA", program_id=prog.id, year_of_study=1, semester=1)
        group_b = StudentGroup(name="Group B", code="GB", program_id=prog.id, year_of_study=1, semester=1)
        lec_a = Lecturer(name="Dr Alpha", email=f"alpha-{suffix}@test.com", department_id=dept.id)
        lec_b = Lecturer(name="Dr Beta", email=f"beta-{suffix}@test.com", department_id=dept.id)
        room = Room(name="Small Room", code=f"SR{suffix}", capacity=25, university_id=uni.id)
        slot1 = TimeSlot(day="Tuesday", start_time="08:00", end_time="09:00", slot_index=0)
        slot2 = TimeSlot(day="Wednesday", start_time="08:00", end_time="09:00", slot_index=1)
        db.session.add_all([group_a, group_b, lec_a, lec_b, room, slot1, slot2])
        db.session.flush()
        course = Course(
            name="Web Technologies",
            code=f"WT{suffix}",
            department_id=dept.id,
            program_id=prog.id,
            lecturer_id=lec_a.id,
            student_count=30,
            semester=1,
            weekly_hours=2,
        )
        course.student_groups = [group_a, group_b]
        tt = Timetable(
            name="Test TT",
            semester=1,
            academic_year="2025-2026",
            department_id=dept.id,
            status="active",
            violation_report=[{"rule": "stale", "message": "old snapshot"}],
        )
        db.session.add_all([course, tt])
        db.session.flush()
        db.session.commit()

        token = create_access_token(
            identity="officer-rc",
            additional_claims={"role": "timetable_officer", "university_id": uni.id},
        )
        return {
            "token": token,
            "timetable_id": tt.id,
            "course_id": course.id,
            "lec_a_id": lec_a.id,
            "lec_b_id": lec_b.id,
            "room_id": room.id,
            "slot1_id": slot1.id,
            "slot2_id": slot2.id,
            "group_a_id": group_a.id,
            "group_b_id": group_b.id,
        }


class TestViolationRecompute:
    def test_no_h1_when_entries_use_different_lecturers(self, client, app):
        from app.extensions import db
        from app.models.domain import TimetableEntry

        ids = _seed_base(app)
        with app.app_context():
            db.session.add(TimetableEntry(
                timetable_id=ids["timetable_id"],
                course_id=ids["course_id"],
                lecturer_id=ids["lec_a_id"],
                room_id=ids["room_id"],
                time_slot_id=ids["slot1_id"],
                student_group_id=ids["group_a_id"],
            ))
            db.session.add(TimetableEntry(
                timetable_id=ids["timetable_id"],
                course_id=ids["course_id"],
                lecturer_id=ids["lec_b_id"],
                room_id=ids["room_id"],
                time_slot_id=ids["slot1_id"],
                student_group_id=ids["group_b_id"],
            ))
            db.session.commit()

        headers = {"Authorization": f"Bearer {ids['token']}"}
        resp = client.get(f"/api/v1/timetable/{ids['timetable_id']}/violations", headers=headers)
        assert resp.status_code == 200
        rules = [v.get("rule", "") for v in resp.get_json()["data"]]
        assert not any("H1" in r for r in rules)

    def test_h1_with_group_labels_when_same_lecturer(self, client, app):
        from app.extensions import db
        from app.models.domain import TimetableEntry

        ids = _seed_base(app)
        with app.app_context():
            db.session.add(TimetableEntry(
                timetable_id=ids["timetable_id"],
                course_id=ids["course_id"],
                lecturer_id=ids["lec_a_id"],
                room_id=ids["room_id"],
                time_slot_id=ids["slot1_id"],
                student_group_id=ids["group_a_id"],
            ))
            db.session.add(TimetableEntry(
                timetable_id=ids["timetable_id"],
                course_id=ids["course_id"],
                lecturer_id=ids["lec_a_id"],
                room_id=ids["room_id"],
                time_slot_id=ids["slot1_id"],
                student_group_id=ids["group_b_id"],
            ))
            db.session.commit()

        headers = {"Authorization": f"Bearer {ids['token']}"}
        resp = client.get(f"/api/v1/timetable/{ids['timetable_id']}/violations", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        h1 = [v for v in data if "H1" in v.get("rule", "")]
        assert len(h1) == 1
        assert "GA" in h1[0]["message"] or "Group A" in h1[0]["message"]
        assert "GB" in h1[0]["message"] or "Group B" in h1[0]["message"]

    def test_violations_update_after_move(self, client, app):
        from app.extensions import db
        from app.models.domain import TimetableEntry

        ids = _seed_base(app)
        with app.app_context():
            entry = TimetableEntry(
                timetable_id=ids["timetable_id"],
                course_id=ids["course_id"],
                lecturer_id=ids["lec_a_id"],
                room_id=ids["room_id"],
                time_slot_id=ids["slot1_id"],
                student_group_id=ids["group_a_id"],
            )
            clash = TimetableEntry(
                timetable_id=ids["timetable_id"],
                course_id=ids["course_id"],
                lecturer_id=ids["lec_a_id"],
                room_id=ids["room_id"],
                time_slot_id=ids["slot1_id"],
                student_group_id=ids["group_b_id"],
            )
            db.session.add_all([entry, clash])
            db.session.commit()
            entry_id = entry.id

        headers = {"Authorization": f"Bearer {ids['token']}"}
        before = client.get(f"/api/v1/timetable/{ids['timetable_id']}/violations", headers=headers)
        assert any("H1" in v.get("rule", "") for v in before.get_json()["data"])

        move_resp = client.patch(
            f"/api/v1/timetable/entries/{entry_id}",
            json={"time_slot_id": ids["slot2_id"]},
            headers=headers,
        )
        assert move_resp.status_code == 200

        after = client.get(f"/api/v1/timetable/{ids['timetable_id']}/violations", headers=headers)
        assert not any("H1" in v.get("rule", "") for v in after.get_json()["data"])

    def test_detect_conflicts_reports_room_over_capacity(self, client, app):
        from app.extensions import db
        from app.models.domain import TimetableEntry

        ids = _seed_base(app)
        with app.app_context():
            db.session.add(TimetableEntry(
                timetable_id=ids["timetable_id"],
                course_id=ids["course_id"],
                lecturer_id=ids["lec_a_id"],
                room_id=ids["room_id"],
                time_slot_id=ids["slot1_id"],
                student_group_id=ids["group_a_id"],
            ))
            db.session.commit()

        headers = {"Authorization": f"Bearer {ids['token']}"}
        resp = client.get(f"/api/v1/timetable/{ids['timetable_id']}/conflicts", headers=headers)
        assert resp.status_code == 200
        rules = [c.get("rule", "") for c in resp.get_json()["data"]]
        assert any("H3" in r for r in rules)
