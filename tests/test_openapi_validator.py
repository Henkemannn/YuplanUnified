import platform
import sys

if platform.system() == "Windows" and sys.version_info >= (3, 13):
    import pytest as _pytest
    _pytest.skip("Skip OpenAPI validator on Windows/Py3.13 (rpds wheels)", allow_module_level=True)

import pytest
from openapi_spec_validator import validate


def test_openapi_validator_passes(client_admin):
    spec = client_admin.get("/openapi.json", headers={"X-User-Role":"admin","X-Tenant-Id":"1"}).get_json()
    validate(spec)  # raises on failure


def test_openapi_invalid_spec_raises():
    # Missing required info.version; validator raises a library-specific error type.
    # We keep a broad Exception catch for now because openapi-spec-validator versions differ in exception class.
    # Lint B017 suppressed via per-file ignore.
    with pytest.raises(Exception):  # noqa: B017
        validate({
            "openapi": "3.0.3",
            "info": {"title": "x"},  # version missing
            "paths": {}
        })
