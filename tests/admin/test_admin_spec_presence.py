"""Test Admin API specification presence and documentation compliance.

Validates that admin endpoints are properly documented and follow established patterns.
"""

from __future__ import annotations

import pytest
from flask import Flask

from core.app_factory import create_app


def test_admin_spec_presence_in_docs():
    """Verify admin.md documentation exists and contains required sections."""
    import os
    
    docs_path = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "admin.md")
    assert os.path.exists(docs_path), "docs/admin.md must exist"
    
    with open(docs_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Required documentation sections
    assert "# Admin Module" in content, "Must have admin module header"
    assert "## Core Flows" in content, "Must document core flows"
    assert "## RBAC Matrix" in content, "Must have RBAC matrix"
    assert "## ETag & Concurrency Examples" in content, "Must document ETag usage"
    assert "## i18n Keys Specification" in content, "Must document i18n keys"
    
    # Specific flow documentation
    assert "Site & Department Management" in content
    assert "Menu Import Pipeline" in content
    assert "Alt2 Bulk Management" in content
    assert "Statistics & Reporting" in content
    
    # RBAC verification
    assert "| Admin | Editor (Staff) | Viewer |" in content
    assert "POST /api/admin/sites" in content
    assert "GET /api/admin/stats" in content


def test_admin_openapi_spec_exists():
    """Verify OpenAPI specification exists for admin endpoints."""
    import os
    
    spec_path = os.path.join(os.path.dirname(__file__), "..", "..", "openapi", "parts", "admin.yml")
    assert os.path.exists(spec_path), "openapi/parts/admin.yml must exist"
    
    with open(spec_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Basic OpenAPI structure
    assert "openapi: 3.0.3" in content
    assert "title: Admin API" in content
    assert "tags:" in content and "- name: admin" in content
    
    # Required endpoints
    endpoints = [
        "/api/admin/stats",
        "/api/admin/sites", 
        "/api/admin/departments",
        "/api/admin/departments/{id}",
        "/api/admin/departments/{id}/notes",
        "/api/admin/departments/{id}/diet-defaults",
        "/api/admin/menu-import",
        "/api/admin/menu-import/{job_id}",
        "/api/admin/alt2"
    ]
    
    for endpoint in endpoints:
        assert endpoint in content, f"Endpoint {endpoint} must be documented"


def test_admin_openapi_if_match_documentation():
    """Verify If-Match headers are documented for write operations."""
    import os
    
    spec_path = os.path.join(os.path.dirname(__file__), "..", "..", "openapi", "parts", "admin.yml")
    with open(spec_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # If-Match should be documented for PUT operations
    assert "If-Match" in content, "If-Match header must be documented"
    assert "required: true" in content, "If-Match must be marked as required"
    assert "optimistic concurrency" in content.lower(), "Must explain optimistic concurrency"


def test_admin_openapi_412_responses():
    """Verify 412 Precondition Failed responses are documented."""
    import os
    
    spec_path = os.path.join(os.path.dirname(__file__), "..", "..", "openapi", "parts", "admin.yml")
    with open(spec_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 412 responses for write operations
    assert "'412':" in content, "412 status must be documented"
    assert "Precondition Failed" in content, "412 description must be present"
    assert "etag_mismatch" in content, "ETag mismatch error type must be documented"


def test_admin_openapi_problem_details():
    """Verify RFC7807 ProblemDetails schema is used."""
    import os
    
    spec_path = os.path.join(os.path.dirname(__file__), "..", "..", "openapi", "parts", "admin.yml")
    with open(spec_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # ProblemDetails schema usage
    assert "ProblemDetails" in content, "ProblemDetails schema must be referenced"
    assert "application/problem+json" in content, "Problem JSON content type must be used"
    
    # Required ProblemDetails fields
    assert "type:" in content and "title:" in content and "status:" in content


def test_admin_feature_flag_key_documented():
    """Verify ff.admin.enabled feature flag key is documented."""
    import os
    
    docs_path = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "admin.md")
    with open(docs_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    assert "ff.admin.enabled" in content, "Feature flag key must be documented"
    assert "Feature Flag Integration" in content, "Feature flag section must exist"


def test_admin_i18n_keys_documented():
    """Verify i18n keys are documented (no hardcoded strings)."""
    import os
    
    docs_path = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "admin.md")
    with open(docs_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Required i18n key categories
    assert "admin.nav.title" in content
    assert "admin.sites.create_title" in content
    assert "admin.departments.create_title" in content
    assert "admin.errors.insufficient_permissions" in content
    assert "admin.success.site_created" in content


def test_admin_phase_a_implementation_notes():
    """Verify Phase A implementation scope is documented."""
    import os
    
    docs_path = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "admin.md")
    with open(docs_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    assert "Phase A (Current)" in content, "Phase A section must exist"
    assert "Phase B (Future)" in content, "Phase B section must exist"
    assert "501 Not Implemented" in content, "Must document 501 responses for Phase A"