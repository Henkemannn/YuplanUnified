def test_invalid_note_payload_returns_400_error_schema(client_admin):
    r = client_admin.post(
        "/notes/", json={"content": "   "}, headers={"X-User-Role": "admin", "X-Tenant-Id": "1"}
    )
    assert r.status_code in (400, 422)
    data = r.get_json()
    assert data.get("status") in (400, 422)
    assert any(s in data.get("type", " ") for s in ["/validation_error", "/bad_request"])
    assert "detail" in data


def test_invalid_task_payload_returns_400_error_schema(client_admin):
    r = client_admin.post(
        "/tasks/", json={"title": "   "}, headers={"X-User-Role": "admin", "X-Tenant-Id": "1"}
    )
    assert r.status_code in (400, 422)
    data = r.get_json()
    assert data.get("status") in (400, 422)
    assert any(s in data.get("type", " ") for s in ["/validation_error", "/bad_request"])
    assert "detail" in data
