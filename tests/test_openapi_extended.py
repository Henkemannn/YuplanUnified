import platform
import sys

if platform.system() == "Windows" and sys.version_info >= (3, 13):
    import pytest as _pytest
    _pytest.skip("Skip OpenAPI validator on Windows/Py3.13 (rpds wheels)", allow_module_level=True)

import json
from pathlib import Path
from typing import Any

from flask import Flask
from openapi_spec_validator import validate_spec

SPEC_PATH = Path("openapi.json")


def load_spec() -> dict[str, Any]:
    if SPEC_PATH.exists():
        text = SPEC_PATH.read_text(encoding="utf-8")
        spec = json.loads(text)
    else:
        # Fallback: build an app and fetch runtime spec (works in local pytest)
        from core.app_factory import create_app  # local import to avoid test collection import cost

        app: Flask = create_app({"TESTING": True, "FEATURE_FLAGS": {"openapi_ui": True}})
        with app.test_client() as c:
            resp = c.get("/openapi.json")
            assert resp.status_code == 200, "/openapi.json not reachable"
            spec = resp.get_json()
            assert isinstance(spec, dict)
    validate_spec(spec)  # structural validation
    return spec


def test_import_okresponse_meta_format_contains_menu():
    spec = load_spec()
    ok_resp = spec["components"]["schemas"]["ImportOkResponse"]
    fmt_enum = ok_resp["properties"]["meta"]["properties"]["format"]["enum"]
    assert "menu" in fmt_enum


def test_415_description_mentions_required_terms_case_insensitive():
    spec = load_spec()
    text = json.dumps(spec).lower()
    assert "415" in text and "unsupported media type" in text


def test_post_import_menu_has_request_example_minimal_payload():
    spec = load_spec()

    path = "/import/menu"
    method = "post"
    content_type = "application/json"

    assert path in spec["paths"], f"Path {path} saknas i spec"
    assert method in spec["paths"][path], f"Method {method} saknas under {path}"

    req_body = spec["paths"][path][method]["requestBody"]
    content = req_body["content"][content_type]

    examples = content.get("examples")
    example = content.get("example")

    assert examples or example, f"Inga examples funna för {method.upper()} {path}"

    def payload_ok(payload: dict) -> bool:
        if not isinstance(payload, dict):
            return False
        items = payload.get("items")
        if not isinstance(items, list) or not items:
            return False
        first = items[0]
        return isinstance(first, dict) and "name" in first

    if examples:
        any_payload = next(iter(examples.values()))["value"]
        assert payload_ok(any_payload), "Exempelpayload uppfyller inte minimikraven"
    else:
        assert payload_ok(example), "Exempelpayload uppfyller inte minimikraven"
