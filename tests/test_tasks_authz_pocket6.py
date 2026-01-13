"""Tasks API authz smoke tests (P6.3 PR D)."""


def test_tasks_unauthorized_no_session(client_no_tenant):
    r = client_no_tenant.get("/tasks/")
    assert r.status_code == 401
    body = r.get_json()
    assert body.get("status") == 401 and body.get("type", "").endswith("unauthorized")


def test_tasks_forbidden_viewer_create(client_admin):
    r = client_admin.post(
        "/tasks/", json={"title": "X"}, headers={"X-User-Role": "viewer", "X-Tenant-Id": "1"}
    )
    assert r.status_code == 403
    body = r.get_json()
    assert body.get("status") == 403 and body.get("detail") == "forbidden"
    assert body.get("required_role") == "editor"


def test_tasks_editor_create_and_list(client_admin):
    create = client_admin.post(
        "/tasks/", json={"title": "Hello"}, headers={"X-User-Role": "editor", "X-Tenant-Id": "1"}
    )
    assert create.status_code == 201
    list_resp = client_admin.get("/tasks/", headers={"X-User-Role": "editor", "X-Tenant-Id": "1"})
    assert list_resp.status_code == 200
    data = list_resp.get_json()
    assert data["ok"] is True and isinstance(data.get("tasks"), list)


def test_tasks_update_tenant_mismatch(client_admin):
    # Create task in tenant 1
    create = client_admin.post(
        "/tasks/", json={"title": "Mismatch"}, headers={"X-User-Role": "editor", "X-Tenant-Id": "1"}
    )
    assert create.status_code == 201
    tid_task_id = (
        create.get_json()["task"]["id"]
        if create.get_json().get("task")
        else create.get_json().get("task_id")
    )
    # Attempt update with different tenant header (simulate mismatch)
    r = client_admin.patch(
        f"/tasks/{tid_task_id}",
        json={"title": "New"},
        headers={"X-User-Role": "editor", "X-Tenant-Id": "999"},
    )
    assert r.status_code == 403
    data = r.get_json()
    assert data.get("detail") == "forbidden"
