import pytest
from flask import Flask

from core.app_factory import create_app
from core.db import create_all, get_session
from core.models import Task


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    root = tmp_path_factory.mktemp("tasks-api-quarantine")
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test",
            "database_url": f"sqlite:///{(root / 'tasks_main.db').as_posix()}",
            "BUILDER_DB_PATH": str(root / "tasks_builder.db"),
            "FORCE_DB_REINIT": True,
        }
    )
    with app.app_context():
        create_all()
    return app


@pytest.fixture()
def client(app: Flask):
    return app.test_client()


@pytest.fixture()
def auth_session(client):
    def _login(role: str, tenant_id: int = 1, user_id: int = 100):
        client.environ_base.update(
            {
                "HTTP_X_USER_ROLE": role,
                "HTTP_X_TENANT_ID": str(tenant_id),
                "HTTP_X_USER_ID": str(user_id),
            }
        )
        with client.session_transaction() as sess:
            sess.update({"role": role, "tenant_id": tenant_id, "user_id": user_id})

    return _login


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/tasks/"),
        ("post", "/tasks/"),
        ("get", "/tasks/1"),
        ("put", "/tasks/1"),
        ("patch", "/tasks/1"),
        ("delete", "/tasks/1"),
    ],
)
@pytest.mark.parametrize("role", ["viewer", "editor", "admin", "superuser"])
def test_legacy_task_routes_are_quarantined(client, auth_session, method, path, role):
    auth_session(role=role)
    response = getattr(client, method)(path, json={"title": "blocked"})
    assert response.status_code == 404
    assert response.get_json()["type"].endswith("/not_found")


def test_legacy_task_routes_do_not_mutate_database(client, auth_session):
    auth_session(role="admin")
    response = client.post("/tasks/", json={"title": "must not persist"})
    assert response.status_code == 404

    with client.application.app_context():
        db = get_session()
        try:
            assert db.query(Task).filter(Task.title == "must not persist").count() == 0
        finally:
            db.close()
