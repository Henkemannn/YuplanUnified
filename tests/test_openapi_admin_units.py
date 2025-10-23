from __future__ import annotations

import json

from core.app_factory import create_app


def openapi_json():
    app = create_app({"TESTING": True})
    with app.test_client() as c:
        rv = c.get("/openapi.json")
        assert rv.status_code == 200
        return rv.get_json()


def test_openapi_has_admin_units_path():
    spec = openapi_json()
    paths = spec["paths"]
    assert "/admin/units" in paths
    get403 = paths["/admin/units"]["get"]["responses"]["403"]
    examples = get403["content"]["application/problem+json"]["examples"]
    assert "viewer_hitting_admin" in examples
    post_security = paths["/admin/units"]["post"]["security"][0]
    assert "CsrfToken" in post_security
