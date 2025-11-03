import platform
import sys

if platform.system() == "Windows" and sys.version_info >= (3, 13):
    import pytest as _pytest
    _pytest.skip("Skip OpenAPI validator on Windows/Py3.13 (rpds wheels)", allow_module_level=True)

def test_spec_contains_notes_tasks_schemas(client_admin):
    spec = client_admin.get("/openapi.json", headers={"X-User-Role":"admin","X-Tenant-Id":"1"}).get_json()
    schemas = spec["components"]["schemas"]
    for name in ["Note","NoteCreate","Task","TaskCreate","TaskStatus"]:
        assert name in schemas
    assert "content" in schemas["Note"]["properties"]
    assert "title" in schemas["Task"]["properties"]
