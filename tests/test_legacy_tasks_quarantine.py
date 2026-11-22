import pytest


LEGACY_ROUTES = [
    ("/tasks/", "get"),
    ("/tasks/", "post"),
    ("/tasks/1", "get"),
    ("/tasks/1", "put"),
    ("/tasks/1", "patch"),
    ("/tasks/1", "delete"),
    ("/export/tasks.csv", "get"),
]


@pytest.mark.parametrize(("path", "method"), LEGACY_ROUTES)
@pytest.mark.parametrize("role", ["viewer", "editor", "admin", "superuser"])
def test_legacy_task_http_surface_is_unavailable(client_admin, path, method, role):
    response = getattr(client_admin, method)(
        path,
        json={"title": "must remain inaccessible"},
        headers={"X-User-Role": role, "X-Tenant-Id": "1"},
    )
    assert response.status_code == 404
    assert "must remain inaccessible" not in response.get_data(as_text=True)


@pytest.mark.parametrize(("path", "method"), LEGACY_ROUTES)
def test_legacy_task_http_surface_is_unavailable_without_session(
    client_no_tenant, path, method
):
    response = getattr(client_no_tenant, method)(path, json={"title": "anonymous"})
    assert response.status_code == 404
    assert "anonymous" not in response.get_data(as_text=True)
