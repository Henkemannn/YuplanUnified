from __future__ import annotations

import platform
import sys

if platform.system() == "Windows" and sys.version_info >= (3, 13):
    import pytest as _pytest
    _pytest.skip("Skip OpenAPI validator on Windows/Py3.13 (rpds wheels)", allow_module_level=True)

import json


def test_import_schema_format_enum_and_415_description(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    spec = json.loads(resp.get_data(as_text=True))

    meta = spec["components"]["schemas"]["ImportOkResponse"]["properties"]["meta"]
    fmt = meta["properties"]["format"]
    # Allow potential future/extended formats (currently includes menu)
    assert set(fmt["enum"]) >= {"csv", "docx", "xlsx"}

    paths = spec["paths"]
    import_paths = [p for p in paths if p.startswith("/import/")]
    assert import_paths, "Expected at least one /import/* path in OpenAPI spec"

    found_415 = False
    for p in import_paths:
        for method in paths[p]:
            resps = paths[p][method].get("responses", {})
            if "415" in resps:
                resp_415 = resps["415"]
                # Allow either direct description or $ref to component
                if "$ref" in resp_415:
                    # If component ref, we can assert component exists later; mark found
                    found_415 = True
                    break
                desc = resp_415.get("description", "").lower()
                assert "unsupported media type" in desc
                found_415 = True
                break
        if found_415:
            break

    assert found_415, "No 415 description found on any /import/* path"
