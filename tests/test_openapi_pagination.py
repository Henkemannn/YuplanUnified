import json
from typing import Any

import pytest

from flask import Flask

from core.app_factory import create_app


def _get_spec(client) -> dict[str, Any]:
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    return json.loads(resp.data.decode("utf-8"))


def test_openapi_contains_pagination_components():
    app: Flask = create_app({'TESTING': True, 'FEATURE_FLAGS': {'openapi_ui': True}})
    with app.test_client() as client:
        spec = _get_spec(client)
        comps = spec.get("components", {}).get("schemas", {})
        assert "PageMeta" in comps, "PageMeta component missing"
        # Allow either pluralization style for flexibility but require tasks & notes specific
        found_tasks = any(k.startswith("PageResponse_Tasks") for k in comps.keys()) or "PageResponse_Tasks" in comps
        found_notes = any(k.startswith("PageResponse_Notes") for k in comps.keys()) or "PageResponse_Notes" in comps
        assert found_tasks, "PageResponse_Tasks component missing"
        assert found_notes, "PageResponse_Notes component missing"


def test_openapi_tasks_and_notes_have_query_params():
    app: Flask = create_app({'TESTING': True, 'FEATURE_FLAGS': {'openapi_ui': True}})
    with app.test_client() as client:
        spec = _get_spec(client)
        paths = spec.get("paths", {})
        for pth in ("/tasks/", "/notes/"):
            assert pth in paths, f"{pth} missing in spec"
            get_op = paths[pth].get("get")
            assert get_op, f"GET operation missing for {pth}"
            params = get_op.get("parameters", [])
            names = {p.get("name") for p in params}
            for required in ("page", "size", "sort", "order"):
                assert required in names, f"Missing query param '{required}' for {pth}"
            # Validate order enum
            order_param = next(p for p in params if p.get("name") == "order")
            schema = order_param.get("schema", {})
            # Enum check (case-insensitive) - should contain asc/desc
            enum_vals = {v.lower() for v in schema.get("enum", [])}
            assert {"asc", "desc"}.issubset(enum_vals), "order param enum must include asc & desc"
