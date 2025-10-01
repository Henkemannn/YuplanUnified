import pytest
from openapi_spec_validator import validate


def test_openapi_validator_passes(client_admin):
    spec = client_admin.get("/openapi.json", headers={"X-User-Role":"admin","X-Tenant-Id":"1"}).get_json()
    validate(spec)  # raises on failure


def test_openapi_invalid_spec_raises():
    # Missing required info.version; validate should raise an exception for invalid spec
    with pytest.raises(Exception):
        validate({
            "openapi": "3.0.3",
            "info": {"title": "x"},  # version missing
            "paths": {}
        })
