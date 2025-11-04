"""Tests for optimistic concurrency control (ETag/If-Match)."""

from __future__ import annotations

from datetime import UTC, datetime

from core.concurrency import (
    compute_etag,
    get_if_match_header,
    make_bad_request_response,
    make_precondition_failed_response,
    set_etag_header,
    validate_if_match,
)


def test_compute_etag_with_timestamp():
    """ETag should be deterministic for same id+timestamp."""
    dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    etag1 = compute_etag(123, dt)
    etag2 = compute_etag(123, dt)
    assert etag1 == etag2
    assert etag1.startswith('W/"')
    assert len(etag1) > 10  # Should have meaningful hash


def test_compute_etag_different_timestamps():
    """Different timestamps should produce different ETags."""
    dt1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    dt2 = datetime(2025, 1, 1, 12, 0, 1, tzinfo=UTC)
    etag1 = compute_etag(123, dt1)
    etag2 = compute_etag(123, dt2)
    assert etag1 != etag2


def test_compute_etag_none_timestamp():
    """None timestamp should be handled gracefully."""
    etag = compute_etag(456, None)
    assert etag.startswith('W/"')


def test_set_etag_header(client_admin):
    """set_etag_header should add ETag to response."""
    from flask import jsonify
    dt = datetime(2025, 1, 1, tzinfo=UTC)
    with client_admin.application.app_context():
        resp = jsonify({"id": 1})
        resp = set_etag_header(resp, 1, dt)
        assert "ETag" in resp.headers
        assert resp.headers["ETag"].startswith('W/"')


def test_get_if_match_header_missing(client_admin):
    """get_if_match_header should return None when header missing."""
    with client_admin.application.test_request_context("/test"):
        result = get_if_match_header()
        assert result is None


def test_get_if_match_header_present(client_admin):
    """get_if_match_header should return header value."""
    with client_admin.application.test_request_context(
        "/test", headers={"If-Match": 'W/"abc123"'}
    ):
        result = get_if_match_header()
        assert result == 'W/"abc123"'


def test_validate_if_match_non_strict_missing_header(client_admin):
    """Non-strict validation should pass when If-Match is missing."""
    dt = datetime(2025, 1, 1, tzinfo=UTC)
    with client_admin.application.test_request_context("/test"):
        valid, error = validate_if_match(1, dt, strict=False)
        assert valid is True
        assert error is None


def test_validate_if_match_strict_missing_header(client_admin):
    """Strict validation should fail when If-Match is missing."""
    dt = datetime(2025, 1, 1, tzinfo=UTC)
    with client_admin.application.test_request_context("/test"):
        valid, error = validate_if_match(1, dt, strict=True)
        assert valid is False
        assert error == "missing"


def test_validate_if_match_matching(client_admin):
    """Validation should pass when If-Match matches current ETag."""
    dt = datetime(2025, 1, 1, tzinfo=UTC)
    current_etag = compute_etag(1, dt)
    with client_admin.application.test_request_context(
        "/test", headers={"If-Match": current_etag}
    ):
        valid, error = validate_if_match(1, dt, strict=True)
        assert valid is True
        assert error is None


def test_validate_if_match_mismatch(client_admin):
    """Validation should fail when If-Match doesn't match."""
    dt = datetime(2025, 1, 1, tzinfo=UTC)
    with client_admin.application.test_request_context(
        "/test", headers={"If-Match": 'W/"wronghash"'}
    ):
        valid, error = validate_if_match(1, dt, strict=True)
        assert valid is False
        assert error == "mismatch"


def test_validate_if_match_strips_quotes(client_admin):
    """Validation should handle quoted and unquoted ETags."""
    dt = datetime(2025, 1, 1, tzinfo=UTC)
    etag = compute_etag(1, dt)
    # Extract hash without W/" prefix and quotes
    etag_hash = etag.split('"')[1]
    
    # Test with various quote formats
    for if_match_value in [
        f'W/"{etag_hash}"',
        f'"{etag_hash}"',
        etag_hash,
    ]:
        with client_admin.application.test_request_context(
            "/test", headers={"If-Match": if_match_value}
        ):
            valid, error = validate_if_match(1, dt, strict=True)
            assert valid is True, f"Failed for If-Match: {if_match_value}"
            assert error is None


def test_make_precondition_failed_response():
    """make_precondition_failed_response should create proper RFC7807 response."""
    payload, status = make_precondition_failed_response("Resource modified")
    assert status == 412
    assert payload["type"] == "about:blank"
    assert payload["title"] == "Precondition Failed"
    assert payload["status"] == 412
    assert payload["detail"] == "Resource modified"


def test_make_precondition_failed_response_no_detail():
    """make_precondition_failed_response should work without detail."""
    payload, status = make_precondition_failed_response()
    assert status == 412
    assert "detail" not in payload


def test_make_bad_request_response():
    """make_bad_request_response should create proper RFC7807 response."""
    invalid_params = [{"name": "If-Match", "reason": "required"}]
    payload, status = make_bad_request_response(
        "If-Match header required", invalid_params
    )
    assert status == 400
    assert payload["type"] == "about:blank"
    assert payload["title"] == "Bad Request"
    assert payload["status"] == 400
    assert payload["detail"] == "If-Match header required"
    assert payload["invalid_params"] == invalid_params


def test_make_bad_request_response_no_params():
    """make_bad_request_response should work without invalid_params."""
    payload, status = make_bad_request_response("Something went wrong")
    assert status == 400
    assert "invalid_params" not in payload
