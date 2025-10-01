def test_404_json_error_schema(client_admin):
    r = client_admin.get("/__no_such_route__", headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    assert r.status_code == 404
    data = r.get_json()
    assert data["error"] == "not_found"
    assert "message" in data


def test_400_json_error_schema(client_admin):
    # provoke 400 by sending invalid JSON to tasks create (title missing)
    r = client_admin.post("/tasks/", json={"task_type":"prep"}, headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    assert r.status_code == 400
    data = r.get_json()
    assert data["error"] in ("validation_error","bad_request")
    assert "message" in data
