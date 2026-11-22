import pytest


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize("role", ["viewer", "editor", "admin", "superuser"])
def test_legacy_task_collection_is_quarantined(client_admin, method, role):
    response = getattr(client_admin, method)(
        "/tasks/",
        json={"title": "blocked"},
        headers={"X-User-Role": role, "X-Tenant-Id": "1"},
    )
    assert response.status_code == 404


@pytest.mark.parametrize("method", ["get", "put", "patch", "delete"])
@pytest.mark.parametrize("role", ["viewer", "editor", "admin", "superuser"])
def test_legacy_task_item_is_quarantined(client_admin, method, role):
    response = getattr(client_admin, method)(
        "/tasks/1",
        json={"title": "blocked"},
        headers={"X-User-Role": role, "X-Tenant-Id": "1"},
    )
    assert response.status_code == 404


def test_legacy_task_route_is_not_authenticated_or_role_gated(client_no_tenant):
    response = client_no_tenant.get("/tasks/")
    assert response.status_code == 404
