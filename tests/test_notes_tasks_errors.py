def test_invalid_note_payload_returns_400_error_schema(client_admin):
    r = client_admin.post("/notes/", json={"content":"   "}, headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    assert r.status_code == 400
    data = r.get_json()
    assert data["error"] in ("validation_error","bad_request")
    assert "message" in data


def test_invalid_task_payload_returns_400_error_schema(client_admin):
    r = client_admin.post("/tasks/", json={"title":"   "}, headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    assert r.status_code == 400
    data = r.get_json()
    assert data["error"] in ("validation_error","bad_request")
    assert "message" in data
