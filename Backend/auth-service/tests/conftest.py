import pytest
from app import create_app
from app.extensions import db as _db


@pytest.fixture(scope="session")
def app():
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        from app.services.auth_service import seed_roles
        seed_roles()
        yield app
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    yield _db
    _db.session.rollback()


@pytest.fixture()
def admin_user(db, app):
    from app.models.user import User, Role
    role = Role.query.filter_by(name="admin").first()
    user = User(
        email="admin@test.com", username="admin", first_name="Admin",
        last_name="User", role_id=role.id, is_verified=True,
    )
    user.set_password("Admin1234")
    db.session.add(user)
    db.session.commit()
    yield user
    db.session.delete(user)
    db.session.commit()
