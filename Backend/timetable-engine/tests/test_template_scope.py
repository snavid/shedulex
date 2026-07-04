import pytest


class TestTemplateUniversityScope:
    def test_create_template_scopes_to_jwt_university(self, client, app):
        from app.extensions import db
        from app.models.domain import University, TimetableTemplate
        from flask_jwt_extended import create_access_token

        with app.app_context():
            uni = University(name="Template Uni", code="TPL")
            db.session.add(uni)
            db.session.flush()
            other = University(name="Other Uni", code="OTH")
            db.session.add(other)
            db.session.commit()
            uni_id = uni.id
            token = create_access_token(
                identity="officer-1",
                additional_claims={"role": "timetable_officer", "university_id": uni_id},
            )

        headers = {"Authorization": f"Bearer {token}"}
        create_resp = client.post(
            "/api/v1/templates",
            json={"name": "Morning Schedule"},
            headers=headers,
        )
        assert create_resp.status_code == 201
        created = create_resp.get_json()["data"]
        assert created["university_id"] == uni_id

        list_resp = client.get("/api/v1/templates", headers=headers)
        assert list_resp.status_code == 200
        names = [t["name"] for t in list_resp.get_json()["data"]]
        assert "Morning Schedule" in names

        with app.app_context():
            stored = TimetableTemplate.query.filter_by(name="Morning Schedule").first()
            assert stored is not None
            assert stored.university_id == uni_id

    def test_list_templates_excludes_other_university(self, client, app):
        from app.extensions import db
        from app.models.domain import University, TimetableTemplate
        from flask_jwt_extended import create_access_token

        with app.app_context():
            uni_a = University(name="Uni A", code="UNA")
            uni_b = University(name="Uni B", code="UNB")
            db.session.add_all([uni_a, uni_b])
            db.session.flush()
            db.session.add(TimetableTemplate(name="A Template", university_id=uni_a.id))
            db.session.add(TimetableTemplate(name="B Template", university_id=uni_b.id))
            db.session.commit()
            token_b = create_access_token(
                identity="officer-b",
                additional_claims={"role": "timetable_officer", "university_id": uni_b.id},
            )

        headers = {"Authorization": f"Bearer {token_b}"}
        list_resp = client.get("/api/v1/templates", headers=headers)
        assert list_resp.status_code == 200
        names = [t["name"] for t in list_resp.get_json()["data"]]
        assert "B Template" in names
        assert "A Template" not in names
