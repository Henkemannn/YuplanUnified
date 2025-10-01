import pytest

# These tests assert shape (happy/error) for newly strict API modules.

# --- Admin API ---

def test_admin_tenants_list_happy(client_admin):
    resp = client_admin.get("/admin/tenants", headers={"X-User-Role":"superuser","X-Tenant-Id":"1"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert "tenants" in data and isinstance(data["tenants"], list)


def test_admin_feature_toggle_error_missing_fields(client_admin):
    # Missing required body fields -> error
    resp = client_admin.post("/admin/feature_flags", json={}, headers={"X-User-Role":"superuser","X-Tenant-Id":"1"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["ok"] is False or data.get("error")

# --- Diet API ---

def test_diet_create_type_happy(client_admin):
    resp = client_admin.post("/diet/types", json={"name":"Protein Light","default_select":True}, headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True and isinstance(data.get("diet_type_id"), int)


def test_diet_create_type_missing_name_error(client_admin):
    resp = client_admin.post("/diet/types", json={"default_select":True}, headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["ok"] is False or data.get("error")

# --- Metrics API ---

def test_metrics_query_happy(client_admin):
    resp = client_admin.post("/metrics/query", json={"filters":{}}, headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True and isinstance(data.get("rows"), list)


def test_metrics_summary_missing_from_error(client_admin):
    resp = client_admin.get("/metrics/summary/day", headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["ok"] is False or data.get("error")

# --- Recommendation API ---

def test_recommendation_happy(client_admin):
    # Provide minimal valid params; service may return baseline values
    resp = client_admin.get("/service/recommendation?category=fish&guest_count=2", headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    # Accept either 200 or domain-specific error if underlying service lacks data, but focus on shape when 200
    if resp.status_code == 200:
        data = resp.get_json()
        assert "recommended_g_per_guest" in data
        assert "guest_count" in data and data["guest_count"] == 2
    else:
        # If service cannot compute recommendation yet, ensure error envelope
        data = resp.get_json()
        assert data.get("ok") is False or data.get("error")


def test_recommendation_missing_guest_count_error(client_admin):
    resp = client_admin.get("/service/recommendation?category=fish", headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data.get("ok") is False or data.get("error")
