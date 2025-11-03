import platform
import sys

if platform.system() == "Windows" and sys.version_info >= (3, 13):
    import pytest as _pytest
    _pytest.skip("Skip OpenAPI validator on Windows/Py3.13 (rpds wheels)", allow_module_level=True)

from core.app_factory import create_app

PROTECTED_PREFIXES = ["/tasks", "/features", "/admin/feature_flags", "/notes"]

def test_openapi_security_elements():
    app = create_app({"TESTING": True})
    with app.test_client() as c:
        spec = c.get("/openapi.json", headers={"X-User-Role":"admin","X-Tenant-Id":"1"}).get_json()
    comps = spec.get("components", {})
    assert "securitySchemes" in comps and "BearerAuth" in comps["securitySchemes"]
    responses = comps.get("responses", {})
    for r in ("Error401","Error403","Error429"):
        assert r in responses, f"Missing reusable response {r}"
    # Check protected paths have security arrays
    for path, item in spec.get("paths", {}).items():
        if any(path.startswith(pref) for pref in PROTECTED_PREFIXES):
            for method, mdata in item.items():
                if method.lower() not in ("get","post","put","delete","patch"): continue
                # Allow some admin or feature endpoints intentionally lacking? Our spec sets all; enforce.
                assert "security" in mdata, f"Missing security for {path} {method}"