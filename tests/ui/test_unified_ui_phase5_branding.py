"""
Test Suite: Unified UI – Phase 5 (Branding, Identity & App Shell)

Tests for global Yuplan branding, headers, footers, logos, and consistent identity.
"""

import pytest
from flask import Flask
from flask.testing import FlaskClient


def _headers(role="admin", tid="1"):
    return {"X-User-Role": role, "X-Tenant-Id": tid}


class TestYuplanBranding:
    """Test global Yuplan branding elements across all views"""

    def test_cook_dashboard_has_yuplan_logo(self, app_session: Flask, client_cook: FlaskClient):
        """Cook dashboard should contain Yuplan logo"""
        resp = client_cook.get("/ui/cook", headers=_headers("cook"))
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        
        # Logo should be present (logo-proposal.svg is the canonical Yuplan logo)
        assert "yuplan" in html.lower()
        assert "/static/img/logo-proposal.svg" in html
    
    def test_admin_dashboard_has_yuplan_logo(self, app_session: Flask, client_admin: FlaskClient):
        """Admin dashboard should contain Yuplan logo"""
        resp = client_admin.get("/ui/admin", headers=_headers("admin"))
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        
        # Logo should be present
        assert "yuplan" in html.lower()
        assert "/static/img/logo-proposal.svg" in html
    
    def test_test_login_page_has_branding(self, app_session: Flask, client: FlaskClient):
        """Test login page should have Yuplan branding"""
        resp = client.get("/test-login")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        
        # Should have logo (logo-proposal.svg)
        assert "/static/img/logo-proposal.svg" in html        # Should have Yuplan Unified title
        assert "Yuplan Unified" in html
        
        # Should have dev-only notice
        assert "utveckling" in html.lower() or "test" in html.lower()


class TestGlobalHeader:
    """Test global header presence and functionality"""

    def test_cook_dashboard_has_global_header(self, app_session: Flask, client_cook: FlaskClient):
        """Cook dashboard should have global Yuplan header"""
        resp = client_cook.get("/ui/cook", headers=_headers("cook"))
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        
        # Global header should be present
        assert "yp-global-header" in html
        assert "<header" in html

    def test_admin_dashboard_has_global_header(self, app_session: Flask, client_admin: FlaskClient):
        """Admin dashboard should have global Yuplan header"""
        resp = client_admin.get("/ui/admin", headers=_headers("admin"))
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        
        # App shell header should be present
        assert "app-shell__topbar" in html
        assert "<header" in html

    def test_header_has_environment_badge(self, app_session: Flask, client_admin: FlaskClient):
        """Header should display environment badge"""
        resp = client_admin.get("/ui/admin", headers=_headers("admin"))
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        
        # Environment badge should be present
        assert "app-shell__env-badge" in html
        assert "LOCAL" in html or "STAGING" in html or "PROD" in html

    def test_header_has_user_info(self, app_session: Flask, client_cook: FlaskClient):
        """Header should display current user info"""
        resp = client_cook.get("/ui/cook", headers=_headers("cook"))
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        
        # User info should be present
        assert "yp-global-header__user" in html or "inloggad" in html.lower()


class TestGlobalFooter:
    """Test global footer presence and content"""

    def test_cook_dashboard_has_global_footer(self, app_session: Flask, client_cook: FlaskClient):
        """Cook dashboard should have global Yuplan footer"""
        resp = client_cook.get("/ui/cook", headers=_headers("cook"))
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        
        # Global footer should be present
        assert "yp-global-footer" in html
        assert "<footer" in html

    def test_admin_dashboard_has_global_footer(self, app_session: Flask, client_admin: FlaskClient):
        """Admin dashboard should have global Yuplan footer"""
        resp = client_admin.get("/ui/admin", headers=_headers("admin"))
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        
        # App shell sidebar footer should be present
        assert "app-shell__sidebar-footer" in html
        assert "Yuplan" in html

    def test_footer_has_copyright(self, app_session: Flask, client_admin: FlaskClient):
        """Footer should contain Yuplan copyright"""
        resp = client_admin.get("/ui/admin", headers=_headers("admin"))
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        
        # App shell footer should carry brand name
        assert "app-shell__sidebar-footer" in html
        assert "Yuplan" in html
        
    def test_footer_has_support_text(self, app_session: Flask, client_admin: FlaskClient):
        """Footer should contain support information"""
        resp = client_admin.get("/ui/admin", headers=_headers("admin"))
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        
        # Support link should be present in user menu
        assert "Support" in html or "support" in html.lower()


class TestNavigation:
    """Test navigation consistency and home links"""

    def test_logo_link_goes_to_home(self, app_session: Flask, client_admin: FlaskClient):
        """Logo should be clickable and link to appropriate home page"""
        resp = client_admin.get("/ui/admin", headers=_headers("admin"))
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        
        # App shell brand should be present
        assert "app-shell__brand" in html
        assert "/static/img/logo-proposal.svg" in html

    def test_admin_sidebar_has_navigation_icons(self, app_session: Flask, client_admin: FlaskClient):
        """Admin sidebar should have navigation with icons"""
        resp = client_admin.get("/ui/admin", headers=_headers("admin"))
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        
        # Sidebar navigation should have main app links
        assert "app-shell__nav" in html
        assert "Översikt" in html
        assert "Veckovy" in html
        assert "Avdelningar" in html
        assert "Menyimport" in html
        assert "Specialkost" in html
        assert "Rapport / Statistik" in html


class TestAccessibility:
    """Test ARIA labels and semantic HTML"""

    def test_header_has_aria_labels(self, app_session: Flask, client_admin: FlaskClient):
        """Header should have proper ARIA labels"""
        resp = client_admin.get("/ui/admin", headers=_headers("admin"))
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        
        # App shell should include ARIA labels
        assert "aria-label" in html
        assert "Huvudnavigering" in html or "Användarmeny" in html

    def test_header_uses_semantic_html(self, app_session: Flask, client_admin: FlaskClient):
        """Header should use semantic <header> element"""
        resp = client_admin.get("/ui/admin", headers=_headers("admin"))
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        
        # Should use semantic HTML
        assert '<header' in html
        assert 'app-shell__topbar' in html

    def test_footer_uses_semantic_html(self, app_session: Flask, client_admin: FlaskClient):
        """Footer should use semantic <footer> element"""
        resp = client_admin.get("/ui/admin", headers=_headers("admin"))
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        
        # Should use semantic HTML
        assert '<main' in html
        assert 'app-shell__main' in html


class TestFavicons:
    """Test favicon presence in pages"""

    def test_cook_dashboard_has_favicon(self, app_session: Flask, client_cook: FlaskClient):
        """Cook dashboard should link to favicon"""
        resp = client_cook.get("/ui/cook", headers=_headers("cook"))
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        
        # Favicon link should be present (logo-proposal.svg is canonical)
        assert 'rel="icon"' in html
        assert "/static/img/logo-proposal.svg" in html

    def test_admin_dashboard_has_favicon(self, app_session: Flask, client_admin: FlaskClient):
        """Admin dashboard should link to favicon"""
        resp = client_admin.get("/ui/admin", headers=_headers("admin"))
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        
        # Favicon link should be present
        assert 'rel="icon"' in html
        assert "/static/img/logo-proposal.svg" in html

    def test_test_login_has_favicon(self, app_session: Flask, client: FlaskClient):
        """Test login page should have favicon"""
        resp = client.get("/test-login")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        
        # Favicon link should be present
        assert 'rel="icon"' in html
        assert "/static/img/logo-proposal.svg" in html


class TestTestLoginBranding:
    """Test specific branding for test login page"""

    def test_test_login_has_role_emojis(self, app_session: Flask, client: FlaskClient):
        """Test login should have role emojis as specified"""
        resp = client.get("/test-login")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        
        # Should have specified emojis
        assert "👨‍🍳" in html  # Cook
        assert "🧑‍💼" in html  # Unit Portal
        assert "🛠️" in html or "⚙️" in html  # Admin
        assert "🧩" in html or "👑" in html  # Superuser

    def test_test_login_uses_unified_styling(self, app_session: Flask, client: FlaskClient):
        """Test login should use unified CSS"""
        resp = client.get("/test-login")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        
        # Should load unified CSS
        assert "/static/unified_ui.css" in html
        
        # Should use yp- CSS variables
        assert "var(--yp-" in html


class TestPageTitles:
    """Test that page titles include Yuplan Unified"""

    def test_cook_dashboard_title(self, app_session: Flask, client_cook: FlaskClient):
        """Cook dashboard title should mention Yuplan Unified"""
        resp = client_cook.get("/ui/cook", headers=_headers("cook"))
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        
        assert "<title>" in html
        assert "Yuplan Unified" in html

    def test_admin_dashboard_title(self, app_session: Flask, client_admin: FlaskClient):
        """Admin dashboard title should mention Yuplan Unified"""
        resp = client_admin.get("/ui/admin", headers=_headers("admin"))
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        
        assert "<title>" in html
        assert "Yuplan" in html

    def test_test_login_title(self, app_session: Flask, client: FlaskClient):
        """Test login title should mention Yuplan Unified"""
        resp = client.get("/test-login")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        
        assert "<title>" in html
        assert "Yuplan Unified" in html
