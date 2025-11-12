"""Test Admin API routes skeleton implementation.

Validates feature flag gating, RBAC enforcement, basic validation, and 501 responses.
"""

from __future__ import annotations

import pytest
from flask import Flask

from core.app_factory import create_app
from core.db import create_all, get_session
from core.models import Tenant
from sqlalchemy import text


def _enable_flag(app: Flask, name: str, enabled: bool = True):
    """Enable/disable feature flag for testing."""
    reg = getattr(app, "feature_registry", None)
    assert reg is not None
    if not reg.has(name):
        reg.add(name)
    reg.set(name, enabled)


def _bootstrap_db(app: Flask):
    """Create schema and seed a tenant for testing."""
    with app.app_context():
        # Use migration tables instead of bare metadata to ensure versioned tables exist
        # Alembic migration 0008 creates sites/departments etc.; for tests we emulate minimal subset if absent.
        create_all()
        db = get_session()
        try:
            # Ensure sites table exists (fallback if migration not run)
            try:
                db.execute(text("SELECT 1 FROM sites LIMIT 1"))
            except Exception:
                db.execute(text("CREATE TABLE IF NOT EXISTS sites (id TEXT PRIMARY KEY, name TEXT NOT NULL, version INTEGER DEFAULT 0, updated_at TEXT)"))
            # Seed tenant if missing (legacy tests depend on tenant_id=1 existence for headers)
            if not db.query(Tenant).first():
                t = Tenant(name="TestTenant")
                db.add(t)
                db.commit()
        finally:
            db.close()


class TestAdminFeatureFlag:
    """Test admin module feature flag behavior (Phase B)."""

    def test_admin_feature_flag_off_returns_404(self):
        """When ff.admin.enabled is false, all admin endpoints return 404."""
        app = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"})
        _bootstrap_db(app)
        _enable_flag(app, "ff.admin.enabled", False)
        client = app.test_client()
        
        # Test with admin headers
        headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
        
        endpoints = [
            "/admin/stats",
            "/admin/sites", 
            "/admin/departments",
            "/admin/menu-import",
            "/admin/alt2"
        ]
        
        for endpoint in endpoints:
            # GET endpoints
            if endpoint in ["/admin/stats"]:
                response = client.get(endpoint, headers=headers)
                assert response.status_code == 404
                assert response.content_type == "application/problem+json"
                data = response.get_json()
                assert data["detail"] == "Admin module is not enabled"
            
            # POST endpoints  
            if endpoint in ["/admin/sites", "/admin/departments", "/admin/menu-import"]:
                response = client.post(endpoint, headers=headers, json={})
                assert response.status_code == 404
                assert response.content_type == "application/problem+json"
            
            # PUT endpoints
            if endpoint in ["/admin/alt2"]:
                response = client.put(endpoint, headers=headers, json={})
                assert response.status_code == 404

    def test_admin_feature_flag_on_allows_access(self):
        """When ff.admin.enabled is true, admin endpoints are accessible and write endpoints work."""
        app = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"})
        _bootstrap_db(app)
        _enable_flag(app, "ff.admin.enabled", True)
        client = app.test_client()
        
        headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
        
        # Stats endpoint should work (not 404)
        response = client.get("/admin/stats", headers=headers)
        assert response.status_code == 200  # GET stats implemented in Phase A
        # Write endpoint now implemented: should return 201
        response = client.post("/admin/sites", headers=headers, json={"name": "Test Site"})
        assert response.status_code == 201
        assert "ETag" in response.headers


class TestAdminRBAC:
    """Test admin module RBAC enforcement (Phase B)."""

    def test_admin_stats_allows_admin_and_editor(self):
        """GET /admin/stats allows admin and editor roles."""
        app = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"})
        _bootstrap_db(app)
        _enable_flag(app, "ff.admin.enabled", True)
        client = app.test_client()
        
        # Admin can access
        response = client.get("/admin/stats", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
        assert response.status_code == 200
        
        # Editor can access
        response = client.get("/admin/stats", headers={"X-User-Role": "editor", "X-Tenant-Id": "1"})
        assert response.status_code == 200

    def test_admin_stats_forbids_viewer(self):
        """GET /admin/stats forbids viewer role."""
        app = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"})
        _bootstrap_db(app)
        _enable_flag(app, "ff.admin.enabled", True)
        client = app.test_client()
        
        response = client.get("/admin/stats", headers={"X-User-Role": "viewer", "X-Tenant-Id": "1"})
        assert response.status_code == 403

    def test_admin_write_endpoints_require_admin_role(self):
        """Write endpoints require admin role only (Phase B implemented)."""
        app = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"})
        _bootstrap_db(app)
        _enable_flag(app, "ff.admin.enabled", True)
        client = app.test_client()
        
        write_endpoints = [
            ("/admin/sites", "post"),
            ("/admin/departments", "post"),
            ("/admin/menu-import", "post"),
        ]
        
        for endpoint, method in write_endpoints:
            # Admin should succeed (201 for create endpoints)
            if method == "post":
                body = {"name": "S"} if endpoint.endswith("sites") else {"name": "D", "site_id": "dummy-site", "resident_count_mode": "fixed"}
                if endpoint.endswith("sites"):
                    response = client.post(endpoint, headers={"X-User-Role": "admin", "X-Tenant-Id": "1"}, json=body)
                    # site creation requires name only
                else:
                    # department will fail without valid UUID site, accept 400 rather than RBAC failure
                    response = client.post(endpoint, headers={"X-User-Role": "admin", "X-Tenant-Id": "1"}, json=body)
                assert response.status_code in (201, 400)
            
            # Editor should get 403 (forbidden)
            if method == "post":
                response = client.post(endpoint, headers={"X-User-Role": "editor", "X-Tenant-Id": "1"}, json={})
            assert response.status_code == 403
            
            # Viewer should get 403 (forbidden)
            if method == "post":
                response = client.post(endpoint, headers={"X-User-Role": "viewer", "X-Tenant-Id": "1"}, json={})
            assert response.status_code == 403


class TestAdminStatsEndpoint:
    """Test GET /admin/stats implementation."""

    def test_admin_stats_returns_minimal_payload(self):
        """GET /admin/stats returns minimal Phase A payload."""
        app = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"})
        _bootstrap_db(app)
        _enable_flag(app, "ff.admin.enabled", True)
        client = app.test_client()
        
        response = client.get("/admin/stats", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
        assert response.status_code == 200
        
        data = response.get_json()
        assert "year" in data
        assert "week" in data 
        assert "departments" in data
        assert data["departments"] == []  # Empty in Phase A

    def test_admin_stats_includes_etag_and_cache_headers(self):
        """GET /admin/stats includes ETag and Cache-Control headers."""
        app = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"})
        _bootstrap_db(app)
        _enable_flag(app, "ff.admin.enabled", True)
        client = app.test_client()
        
        response = client.get("/admin/stats", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
        assert response.status_code == 200
        
        # ETag header
        assert "ETag" in response.headers
        etag = response.headers["ETag"]
        assert etag.startswith('W/"admin:stats:')
        assert ":v0" in etag  # Phase A version
        
        # Cache-Control header
        assert "Cache-Control" in response.headers
        assert response.headers["Cache-Control"] == "private, max-age=0, must-revalidate"

    def test_admin_stats_supports_conditional_get(self):
        """GET /admin/stats supports 304 Not Modified with If-None-Match."""
        app = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"})
        _bootstrap_db(app)
        _enable_flag(app, "ff.admin.enabled", True)
        client = app.test_client()
        
        headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
        
        # First request to get ETag
        response = client.get("/admin/stats", headers=headers)
        assert response.status_code == 200
        etag = response.headers["ETag"]
        
        # Second request with If-None-Match
        headers["If-None-Match"] = etag
        response = client.get("/admin/stats", headers=headers)
        assert response.status_code == 304
        assert len(response.data) == 0  # Empty body for 304

    def test_admin_stats_validates_year_parameter(self):
        """GET /admin/stats validates year parameter range."""
        app = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"})
        _bootstrap_db(app)
        _enable_flag(app, "ff.admin.enabled", True)
        client = app.test_client()
        
        headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
        
        # Invalid year (too low)
        response = client.get("/admin/stats?year=1969", headers=headers)
        assert response.status_code == 400
        data = response.get_json()
        assert "Year must be between 1970 and 2100" in data["detail"]
        
        # Invalid year (too high)
        response = client.get("/admin/stats?year=2101", headers=headers)
        assert response.status_code == 400
        
        # Valid year
        response = client.get("/admin/stats?year=2025", headers=headers)
        assert response.status_code == 200

    def test_admin_stats_validates_week_parameter(self):
        """GET /admin/stats validates week parameter range."""
        app = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"})
        _bootstrap_db(app)
        _enable_flag(app, "ff.admin.enabled", True)
        client = app.test_client()
        
        headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
        
        # Invalid week (too low)
        response = client.get("/admin/stats?week=0", headers=headers)
        assert response.status_code == 400
        data = response.get_json()
        assert "Week must be between 1 and 53" in data["detail"]
        
        # Invalid week (too high) 
        response = client.get("/admin/stats?week=54", headers=headers)
        assert response.status_code == 400
        
        # Valid week
        response = client.get("/admin/stats?week=45", headers=headers)
        assert response.status_code == 200


class TestAdminWriteEndpoints:
    """Phase B: PUT endpoints require If-Match and respond appropriately."""

    def test_put_endpoints_require_if_match_header(self):
        """PUT endpoints validate If-Match header presence (Phase B)."""
        app = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"})
        _bootstrap_db(app)
        _enable_flag(app, "ff.admin.enabled", True)
        client = app.test_client()
        
        headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
        
        put_endpoints = [
            "/admin/departments/uuid-123",
            "/admin/departments/uuid-123/notes",
            "/admin/departments/uuid-123/diet-defaults",
            "/admin/alt2"
        ]
        
        for endpoint in put_endpoints:
            response = client.put(endpoint, headers=headers, json={})
            assert response.status_code == 400
            headers_with_etag = headers.copy()
            headers_with_etag["If-Match"] = 'W/"admin:dept:uuid-123:v0"'
            response = client.put(endpoint, headers=headers_with_etag, json={})
            # Department IDs will not exist yet → may be 412 or 404 depending on implementation; allow 400/412/404
            assert response.status_code in (400, 412, 404)

    def test_menu_import_job_status_endpoint(self):
        """GET /admin/menu-import/{job_id} allows admin/editor access."""
        app = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"})
        _bootstrap_db(app)
        _enable_flag(app, "ff.admin.enabled", True)
        client = app.test_client()
        
        # Admin can access
        response = client.get("/admin/menu-import/uuid-123", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
        assert response.status_code == 501  # Not implemented but authorized
        
        # Editor can access  
        response = client.get("/admin/menu-import/uuid-123", headers={"X-User-Role": "editor", "X-Tenant-Id": "1"})
        assert response.status_code == 501  # Not implemented but authorized
        
        # Viewer cannot access
        response = client.get("/admin/menu-import/uuid-123", headers={"X-User-Role": "viewer", "X-Tenant-Id": "1"})
        assert response.status_code == 403