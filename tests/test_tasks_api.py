import pytest
from flask import Flask

from core.app_factory import create_app


@pytest.fixture(scope="module")
def app():
    return create_app({"TESTING": True, "SECRET_KEY": "test"})


@pytest.fixture()
def client(app: Flask):
    return app.test_client()


@pytest.fixture()
def auth_session(client):
    """Lightweight helper to set session-like context.
    Assumes app uses cookie-based session; we simulate via test client context.
    """
    def _login(role: str = "admin", tenant_id: int = 1, user_id: int = 100):
        with client.session_transaction() as sess:  # type: ignore[attr-defined]
            sess["role"] = role
            sess["tenant_id"] = tenant_id
            sess["user_id"] = user_id
    return _login


# GIVEN: authenticated session for tenant 1, role "admin"
# WHEN: creating a task with title
# THEN: TaskCreateResponse shape with ok True and int task_id
def test_create_task_happy(client, auth_session):
    auth_session(role="admin", tenant_id=1, user_id=101)
    resp = client.post("/tasks/", json={"title": "Prep menu", "assignee": "alice"})
    assert resp.status_code in (200, 201)
    body = resp.get_json()
    assert body["ok"] is True
    assert isinstance(body.get("task_id"), int)


# GIVEN: at least one task exists in tenant 1
# WHEN: listing tasks
# THEN: TaskListResponse and contains TaskSummary fields
def test_list_tasks_happy(client, auth_session):
    auth_session(role="admin", tenant_id=1, user_id=102)
    client.post("/tasks/", json={"title": "Inventory"})
    resp = client.get("/tasks/")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    tasks = body.get("tasks")
    assert isinstance(tasks, list) and tasks
    t = tasks[0]
    for key in ("id", "title", "status", "owner"):
        assert key in t


# GIVEN: missing title
# WHEN: creating task without title
# THEN: ErrorResponse
def test_create_task_missing_title(client, auth_session):
    auth_session(role="admin", tenant_id=1, user_id=103)
    resp = client.post("/tasks/", json={})
    assert resp.status_code in (400, 422)
    body = resp.get_json()
    assert body.get("status") in (400,422) and body.get("type","" ).startswith("https://example.com/errors/")


# GIVEN: a valid task
# WHEN: updating with invalid status
# THEN: ErrorResponse 400/422
@pytest.mark.parametrize("bad", ["", "invalid", "TODO", None])
def test_update_task_invalid_status(client, auth_session, bad):
    auth_session(role="admin", tenant_id=1, user_id=104)
    tid = client.post("/tasks/", json={"title": "X"}).get_json()["task_id"]
    resp = client.patch(f"/tasks/{tid}", json={"status": bad})
    assert resp.status_code in (400, 422)
    body = resp.get_json()
    assert body.get("status") in (400,422)


# GIVEN: task belongs to tenant 1
# WHEN: user from tenant 999 tries to update
# THEN: 403
def test_update_task_wrong_tenant_forbidden(client, auth_session):
    auth_session(role="admin", tenant_id=1, user_id=105)
    tid = client.post("/tasks/", json={"title": "X"}).get_json()["task_id"]
    # switch tenant context
    auth_session(role="admin", tenant_id=999, user_id=9999)
    resp = client.patch(f"/tasks/{tid}", json={"status": "doing"})
    assert resp.status_code == 403
    body = resp.get_json()
    assert body.get("status") == 403


# GIVEN: viewer role lacks permission
# WHEN: viewer tries to update task
# THEN: 403
def test_update_task_role_forbidden(client, auth_session):
    auth_session(role="admin", tenant_id=1, user_id=106)
    tid = client.post("/tasks/", json={"title": "Y"}).get_json()["task_id"]
    auth_session(role="viewer", tenant_id=1, user_id=200)
    resp = client.patch(f"/tasks/{tid}", json={"status": "done"})
    assert resp.status_code == 403
    body = resp.get_json()
    assert body.get("status") == 403 and body.get("type"," ").endswith("/forbidden")


# NEW: unknown task id returns not_found envelope
def test_update_unknown_task_not_found(client, auth_session):
    auth_session(role="admin", tenant_id=1, user_id=300)
    resp = client.patch("/tasks/999999", json={"status": "done"})
    assert resp.status_code == 404
    body = resp.get_json()
    assert body.get("status") == 404


# NEW: tenant isolation list (tenant B cannot see tenant A tasks)
def test_list_tenant_isolation(client, auth_session):
    auth_session(role="admin", tenant_id=10, user_id=400)
    client.post("/tasks/", json={"title": "A-only"})
    auth_session(role="admin", tenant_id=11, user_id=401)
    resp = client.get("/tasks/")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    titles = {t["title"] for t in body.get("tasks", [])}
    assert "A-only" not in titles


# NEW: role create forbidden (viewer cannot POST)
def test_create_task_role_forbidden(client, auth_session):
    auth_session(role="viewer", tenant_id=1, user_id=500)
    resp = client.post("/tasks/", json={"title": "Z"})
    assert resp.status_code == 403
    body = resp.get_json()
    assert body.get("status") == 403


# NEW: bad status type (int) -> validation error
def test_update_task_bad_status_type(client, auth_session):
    auth_session(role="admin", tenant_id=1, user_id=600)
    tid = client.post("/tasks/", json={"title": "TypeTest"}).get_json()["task_id"]
    resp = client.patch(f"/tasks/{tid}", json={"status": 123})
    assert resp.status_code in (400, 422)
    body = resp.get_json()
    assert body.get("status") in (400,422)

