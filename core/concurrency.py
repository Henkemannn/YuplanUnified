"""Optimistic concurrency control helpers using ETag/If-Match.

This module provides utilities for implementing optimistic locking with HTTP ETags.
ETags are computed from entity state (typically updated_at timestamp + id).
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from flask import Response, request


def compute_etag(entity_id: int | str, updated_at: datetime | None) -> str:
    """Compute ETag from entity id and updated_at timestamp.
    
    Args:
        entity_id: Unique identifier for the entity
        updated_at: Last update timestamp (None treated as epoch)
    
    Returns:
        ETag string in format: W/"<hash>"
        
    Examples:
        >>> from datetime import datetime, UTC
        >>> dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        >>> etag = compute_etag(123, dt)
        >>> etag.startswith('W/"')
        True
    """
    # Use ISO format for timestamp to ensure consistency
    ts_str = updated_at.isoformat() if updated_at else "1970-01-01T00:00:00"
    raw = f"{entity_id}:{ts_str}"
    # Use first 16 chars of sha256 for compact but collision-resistant tag
    hash_val = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f'W/"{hash_val}"'


def set_etag_header(resp: Response, entity_id: int | str, updated_at: datetime | None) -> Response:
    """Add ETag header to response.
    
    Args:
        resp: Flask response object
        entity_id: Entity identifier
        updated_at: Entity last update timestamp
        
    Returns:
        Modified response object with ETag header
    """
    etag = compute_etag(entity_id, updated_at)
    resp.headers["ETag"] = etag
    return resp


def get_if_match_header() -> str | None:
    """Extract If-Match header from current request.
    
    Returns:
        If-Match header value or None if not present
    """
    return request.headers.get("If-Match")


def _normalize_etag(etag: str) -> str:
    """Normalize an ETag by removing quotes and W/ prefix.
    
    Args:
        etag: ETag string (e.g., 'W/"abc"', '"abc"', or 'abc')
        
    Returns:
        Normalized ETag hash without quotes or W/ prefix
    """
    # Strip whitespace and outer quotes
    clean = etag.strip().strip('"')
    
    # Handle weak ETags (W/"...") - strip the W/ prefix and quotes
    if clean.startswith("W/"):
        clean = clean[2:].strip('"')
    
    return clean


def validate_if_match(
    entity_id: int | str,
    updated_at: datetime | None,
    *,
    strict: bool = False,
) -> tuple[bool, str | None]:
    """Validate If-Match header against entity state.
    
    Args:
        entity_id: Entity identifier
        updated_at: Entity last update timestamp
        strict: If True, missing If-Match is treated as validation failure
        
    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if validation passes
        - (False, "missing") if If-Match header missing and strict=True
        - (False, "mismatch") if If-Match doesn't match computed ETag
        
    Examples:
        >>> from datetime import datetime, UTC
        >>> dt = datetime(2025, 1, 1, tzinfo=UTC)
        >>> # Without If-Match header (non-strict)
        >>> validate_if_match(1, dt, strict=False)
        (True, None)
        >>> # Without If-Match header (strict)
        >>> validate_if_match(1, dt, strict=True)
        (False, 'missing')
    """
    if_match = get_if_match_header()
    
    if if_match is None:
        if strict:
            return (False, "missing")
        return (True, None)
    
    current_etag = compute_etag(entity_id, updated_at)
    
    # Normalize both ETags for comparison
    if_match_clean = _normalize_etag(if_match)
    current_clean = _normalize_etag(current_etag)
    
    if if_match_clean != current_clean:
        return (False, "mismatch")
    
    return (True, None)


def make_precondition_failed_response(detail: str | None = None) -> tuple[dict[str, Any], int]:
    """Create RFC7807 problem response for 412 Precondition Failed.
    
    Args:
        detail: Optional detail message
        
    Returns:
        Tuple of (response_dict, status_code)
    """
    payload: dict[str, Any] = {
        "type": "about:blank",
        "title": "Precondition Failed",
        "status": 412,
    }
    if detail:
        payload["detail"] = detail
    return payload, 412


def make_bad_request_response(detail: str, invalid_params: list[dict[str, str]] | None = None) -> tuple[dict[str, Any], int]:
    """Create RFC7807 problem response for 400 Bad Request.
    
    Args:
        detail: Detail message
        invalid_params: Optional list of invalid parameter descriptions
        
    Returns:
        Tuple of (response_dict, status_code)
    """
    payload: dict[str, Any] = {
        "type": "about:blank",
        "title": "Bad Request",
        "status": 400,
        "detail": detail,
    }
    if invalid_params:
        payload["invalid_params"] = invalid_params
    return payload, 400
