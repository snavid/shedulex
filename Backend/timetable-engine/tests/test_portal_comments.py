import pytest


class TestPortalComments:
    def test_create_and_list_comment(self, client, app):
        from app.extensions import db
        from app.models.domain import (
            University, Department, Program, StudentGroup, Course,
            Lecturer, Room, TimeSlot, Timetable, TimetableEntry,
        )
        from flask_jwt_extended import create_access_token

        with app.app_context():
            uni = University(name="Test Uni", code="TST")
            db.session.add(uni)
            db.session.flush()
            dept = Department(name="CS", code="CS", university_id=uni.id)
            db.session.add(dept)
            db.session.flush()
            prog = Program(name="BCS", code="BCS", department_id=dept.id)
            db.session.add(prog)
            db.session.flush()
            group = StudentGroup(name="Group A", code="GA", program_id=prog.id, year_of_study=1, semester=1)
            lec = Lecturer(name="Dr Test", email="lec@test.com", department_id=dept.id)
            room = Room(name="R1", code="R1", capacity=30, university_id=uni.id)
            slot = TimeSlot(day="Monday", start_time="08:00", end_time="09:00")
            db.session.add_all([group, lec, room, slot])
            db.session.flush()
            course = Course(name="Intro", code="CS101", department_id=dept.id, program_id=prog.id, lecturer_id=lec.id)
            db.session.add(course)
            db.session.flush()
            tt = Timetable(name="Sem 1", semester=1, academic_year="2025-2026", department_id=dept.id, status="active")
            db.session.add(tt)
            db.session.flush()
            entry = TimetableEntry(
                timetable_id=tt.id,
                course_id=course.id,
                lecturer_id=lec.id,
                room_id=room.id,
                time_slot_id=slot.id,
                student_group_id=group.id,
            )
            db.session.add(entry)
            db.session.commit()
            entry_id = entry.id
            portal_token = create_access_token(
                identity="student-1",
                additional_claims={
                    "role": "student",
                    "portal": True,
                    "student_group_id": group.id,
                    "registration_number": "REG001",
                    "first_name": "Test",
                    "last_name": "Student",
                    "university_id": uni.id,
                },
            )

        headers = {"Authorization": f"Bearer {portal_token}"}
        create_resp = client.post(
            "/api/v1/portal/comments",
            json={"entry_id": entry_id, "body": "Great lecture!"},
            headers=headers,
        )
        assert create_resp.status_code == 201

        list_resp = client.get("/api/v1/portal/comments", headers=headers)
        assert list_resp.status_code == 200
        assert len(list_resp.get_json()["data"]) == 1

    def test_hidden_comments_not_visible_to_student(self, client, app):
        from app.extensions import db
        from app.models.domain import (
            University, Department, Program, StudentGroup, Course,
            Lecturer, Room, TimeSlot, Timetable, TimetableEntry, TimetableComment,
        )
        from flask_jwt_extended import create_access_token

        with app.app_context():
            uni = University(name="Test Uni Hidden", code="TSTH")
            db.session.add(uni)
            db.session.flush()
            dept = Department(name="CS Hidden", code="CSH", university_id=uni.id)
            db.session.add(dept)
            db.session.flush()
            prog = Program(name="BCS Hidden", code="BCSH", department_id=dept.id)
            db.session.add(prog)
            db.session.flush()
            group = StudentGroup(name="Group H", code="GAH", program_id=prog.id, year_of_study=1, semester=1)
            lec = Lecturer(name="Dr Hidden", email="hidden@test.com", department_id=dept.id)
            room = Room(name="R1H", code="R1H", capacity=30, university_id=uni.id)
            slot = TimeSlot(day="Monday", start_time="08:00", end_time="09:00")
            db.session.add_all([prog, group, lec, room, slot])
            db.session.flush()
            course = Course(name="Intro Hidden", code="CS101H", department_id=dept.id, program_id=prog.id, lecturer_id=lec.id)
            tt = Timetable(name="Sem 1", semester=1, academic_year="2025-2026", department_id=dept.id, status="active")
            db.session.add_all([course, tt])
            db.session.flush()
            entry = TimetableEntry(
                timetable_id=tt.id,
                course_id=course.id,
                lecturer_id=lec.id,
                room_id=room.id,
                time_slot_id=slot.id,
                student_group_id=group.id,
            )
            db.session.add(entry)
            db.session.flush()
            db.session.add(TimetableComment(
                entry_id=entry.id,
                timetable_id=tt.id,
                student_user_id="student-1",
                registration_number="REG001",
                student_name="Test Student",
                body="Visible comment",
                status="visible",
            ))
            db.session.add(TimetableComment(
                entry_id=entry.id,
                timetable_id=tt.id,
                student_user_id="student-1",
                registration_number="REG001",
                student_name="Test Student",
                body="Hidden comment",
                status="hidden",
            ))
            db.session.commit()
            portal_token = create_access_token(
                identity="student-1",
                additional_claims={
                    "role": "student",
                    "portal": True,
                    "student_group_id": group.id,
                    "registration_number": "REG001",
                    "first_name": "Test",
                    "last_name": "Student",
                    "university_id": uni.id,
                },
            )

        headers = {"Authorization": f"Bearer {portal_token}"}
        list_resp = client.get("/api/v1/portal/comments", headers=headers)
        assert list_resp.status_code == 200
        bodies = [c["body"] for c in list_resp.get_json()["data"]]
        assert "Visible comment" in bodies
        assert "Hidden comment" not in bodies

    def test_portal_semester_timetables(self, client, app):
        from app.extensions import db
        from app.models.domain import (
            University, Department, Program, StudentGroup, Course,
            Lecturer, Room, TimeSlot, Timetable, TimetableEntry,
        )
        from flask_jwt_extended import create_access_token

        with app.app_context():
            uni = University(name="Test Uni Semesters", code="TSTS")
            db.session.add(uni)
            db.session.flush()
            dept = Department(name="CS Sem", code="CSS", university_id=uni.id)
            db.session.add(dept)
            db.session.flush()
            prog = Program(name="BCS Sem", code="BCSS", department_id=dept.id)
            db.session.add(prog)
            db.session.flush()
            group = StudentGroup(name="Group S", code="GAS", program_id=prog.id, year_of_study=1, semester=1)
            lec = Lecturer(name="Dr Sem", email="sem@test.com", department_id=dept.id)
            room = Room(name="R1S", code="R1S", capacity=30, university_id=uni.id)
            slot1 = TimeSlot(day="Monday", start_time="08:00", end_time="09:00")
            slot2 = TimeSlot(day="Tuesday", start_time="10:00", end_time="11:00")
            db.session.add_all([prog, group, lec, room, slot1, slot2])
            db.session.flush()
            course1 = Course(name="Intro S1", code="CS101S", department_id=dept.id, program_id=prog.id, lecturer_id=lec.id)
            course2 = Course(name="Data S2", code="CS102S", department_id=dept.id, program_id=prog.id, lecturer_id=lec.id)
            tt1 = Timetable(name="Sem 1 TT", semester=1, academic_year="2025-2026", department_id=dept.id, status="active")
            tt2 = Timetable(name="Sem 2 TT", semester=2, academic_year="2025-2026", department_id=dept.id, status="active")
            db.session.add_all([course1, course2, tt1, tt2])
            db.session.flush()
            db.session.add_all([
                TimetableEntry(
                    timetable_id=tt1.id, course_id=course1.id, lecturer_id=lec.id,
                    room_id=room.id, time_slot_id=slot1.id, student_group_id=group.id,
                ),
                TimetableEntry(
                    timetable_id=tt2.id, course_id=course2.id, lecturer_id=lec.id,
                    room_id=room.id, time_slot_id=slot2.id, student_group_id=group.id,
                ),
            ])
            db.session.commit()
            portal_token = create_access_token(
                identity="student-1",
                additional_claims={
                    "role": "student",
                    "portal": True,
                    "student_group_id": group.id,
                    "registration_number": "REG001",
                    "first_name": "Test",
                    "last_name": "Student",
                    "university_id": uni.id,
                },
            )

        headers = {"Authorization": f"Bearer {portal_token}"}
        sem_resp = client.get("/api/v1/portal/timetable/semesters", headers=headers)
        assert sem_resp.status_code == 200
        semesters = sem_resp.get_json()["data"]
        assert len(semesters) == 2

        sem1 = client.get("/api/v1/portal/timetable?semester=1", headers=headers)
        assert sem1.status_code == 200
        assert len(sem1.get_json()["data"]) == 1
        assert sem1.get_json()["data"][0]["semester"] == 1

        sem2 = client.get("/api/v1/portal/timetable?semester=2", headers=headers)
        assert sem2.status_code == 200
        assert len(sem2.get_json()["data"]) == 1
        assert sem2.get_json()["data"][0]["semester"] == 2

    def test_semesters_include_department_timetables_without_group_entries(self, client, app):
        from app.extensions import db
        from app.models.domain import (
            University, Department, Program, StudentGroup, Course,
            Lecturer, Room, TimeSlot, Timetable, TimetableEntry,
        )
        from flask_jwt_extended import create_access_token

        with app.app_context():
            uni = University(name="Dept Wide Uni", code="DWU")
            db.session.add(uni)
            db.session.flush()
            dept = Department(name="CS Dept", code="CSD", university_id=uni.id)
            db.session.add(dept)
            db.session.flush()
            prog = Program(name="BCS Dept", code="BCSD", department_id=dept.id)
            db.session.add(prog)
            db.session.flush()
            group = StudentGroup(name="Group A Dept", code="GAD", program_id=prog.id, year_of_study=1, semester=1)
            lec = Lecturer(name="Dr A", email="a-dept@test.com", department_id=dept.id)
            room = Room(name="R1 Dept", code="R1DWU", capacity=30, university_id=uni.id)
            slot = TimeSlot(day="Monday", start_time="08:00", end_time="09:00")
            db.session.add_all([prog, group, lec, room, slot])
            db.session.flush()
            course = Course(name="Intro", code="CS101", department_id=dept.id, program_id=prog.id, lecturer_id=lec.id)
            tt1 = Timetable(name="Sem 1", semester=1, academic_year="2025-2026", department_id=dept.id, status="active")
            tt2 = Timetable(name="Sem 2", semester=2, academic_year="2025-2026", department_id=dept.id, status="active")
            db.session.add_all([course, tt1, tt2])
            db.session.flush()
            db.session.add(
                TimetableEntry(
                    timetable_id=tt1.id,
                    course_id=course.id,
                    lecturer_id=lec.id,
                    room_id=room.id,
                    time_slot_id=slot.id,
                    student_group_id=group.id,
                )
            )
            db.session.commit()
            tt2_id = tt2.id
            portal_token = create_access_token(
                identity="student-2",
                additional_claims={
                    "role": "student",
                    "portal": True,
                    "student_group_id": group.id,
                    "registration_number": "REG002",
                    "first_name": "Dept",
                    "last_name": "Student",
                    "university_id": uni.id,
                },
            )

        headers = {"Authorization": f"Bearer {portal_token}"}
        sem_resp = client.get("/api/v1/portal/timetable/semesters", headers=headers)
        assert sem_resp.status_code == 200
        semesters = sem_resp.get_json()["data"]
        assert len(semesters) == 2

        empty_sem2 = client.get(
            f"/api/v1/portal/timetable?timetable_id={tt2_id}&semester=2",
            headers=headers,
        )
        assert empty_sem2.status_code == 200
        assert empty_sem2.get_json()["data"] == []

    def test_delete_timetable_with_comments(self, client, app):
        from app.extensions import db
        from app.models.domain import (
            University, Department, Program, StudentGroup, Course,
            Lecturer, Room, TimeSlot, Timetable, TimetableEntry, TimetableComment,
        )

        with app.app_context():
            uni = University(name="Delete Uni", code="DEL")
            db.session.add(uni)
            db.session.flush()
            dept = Department(name="CS Del", code="CSD", university_id=uni.id)
            db.session.add(dept)
            db.session.flush()
            prog = Program(name="BCS Del", code="BCSD", department_id=dept.id)
            db.session.add(prog)
            db.session.flush()
            group = StudentGroup(name="Group D", code="GAD", program_id=prog.id, year_of_study=1, semester=1)
            lec = Lecturer(name="Dr Delete", email="del@test.com", department_id=dept.id)
            room = Room(name="R1D", code="R1D", capacity=30, university_id=uni.id)
            slot = TimeSlot(day="Monday", start_time="08:00", end_time="09:00")
            db.session.add_all([group, lec, room, slot])
            db.session.flush()
            course = Course(name="Intro Del", code="CS101D", department_id=dept.id, program_id=prog.id, lecturer_id=lec.id)
            tt = Timetable(name="Sem 1 Del", semester=1, academic_year="2025-2026", department_id=dept.id, status="active")
            db.session.add_all([course, tt])
            db.session.flush()
            entry = TimetableEntry(
                timetable_id=tt.id,
                course_id=course.id,
                lecturer_id=lec.id,
                room_id=room.id,
                time_slot_id=slot.id,
                student_group_id=group.id,
            )
            db.session.add(entry)
            db.session.flush()
            db.session.add(TimetableComment(
                entry_id=entry.id,
                timetable_id=tt.id,
                student_user_id="student-del",
                registration_number="REGDEL",
                student_name="Delete Student",
                body="Comment on entry",
                status="visible",
            ))
            db.session.commit()
            timetable_id = tt.id
            entry_id = entry.id

        headers = {"X-Internal-Service-Key": "dev-internal-service-key"}
        resp = client.delete(f"/api/v1/timetable/{timetable_id}", headers=headers)
        assert resp.status_code == 200

        with app.app_context():
            assert Timetable.query.get(timetable_id) is None
            assert TimetableEntry.query.get(entry_id) is None
            assert TimetableComment.query.filter_by(timetable_id=timetable_id).count() == 0
