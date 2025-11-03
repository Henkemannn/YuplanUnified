from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime
from hashlib import sha1
from typing import NotRequired, TypedDict

from flask import Response, jsonify


def _iso_str(dt: datetime | None) -> str:
    """Return ISO string exactly as stored/returned by SQLAlchemy.

    We do NOT coerce timezone or add offsets; this must match tests that
    compute ETags using ts.isoformat() directly from the DB value.
    """
    if dt is None:
        return ""
    return dt.isoformat()


def user_etag(user_id: object, updated_at: datetime | None) -> str:
    """Compute weak ETag from ``user_id`` and ``updated_at.isoformat()``.

    Contract:
    - Uses exactly ``updated_at.isoformat()`` without timezone coercion or normalization.
    - When ``updated_at`` is None, an empty string is used.
    - Format: ``W/"<sha1(f"{id}:{iso}")>"``.
    """
    iso = _iso_str(updated_at)
    raw = f"{user_id}:{iso}".encode()
    digest = sha1(raw).hexdigest()
    return f'W/"{digest}"'


def _normalize_tag(tag: str) -> str:
    t = tag.strip()
    if not t:
        return ""
    if t == "*":
        return t
    # Strip weak prefix
    if t.lower().startswith("w/"):
        t = t[2:].lstrip()
    # Ensure quotes removed
    if t.startswith('"') and t.endswith('"') and len(t) >= 2:
        t = t[1:-1]
    return t


def parse_if_match(header_value: str | None) -> set[str]:
    """Parse If-Match header into a set of normalized tags.

    - Supports multiple comma-separated values
    - Accepts weak validators (W/") and strips the prefix
    - Keeps '*' literal to indicate any representation is acceptable
    - Returns empty set if header is missing or blank
    """
    if not header_value:
        return set()
    parts: Iterable[str] = (p for p in header_value.split(","))
    tags: set[str] = set()
    for p in parts:
        n = _normalize_tag(p)
        if n:
            tags.add(n)
    return tags


_ETAG_TOKEN_RE = re.compile(r"^\s*(\*|W\s*/\s*\"[^\"]*\"|\"[^\"]*\")\s*$", re.IGNORECASE)


def parse_etag_header(header_value: str | None, *, allow_star: bool = True) -> set[str]:
    """Strictly parse an ETag header (If-Match / If-None-Match).

    Valid tokens:
      - "\"...\"" (quotes required)
      - "W/\"...\"" (weak validators)
      - "*" (only when allow_star=True)

    Raises ValueError when header is present but contains no valid tokens or any invalid token (including empty \"\").
    Returns empty set when header is missing (None or empty string).
    """
    if header_value is None or header_value.strip() == "":
        return set()
    tokens = [t.strip() for t in header_value.split(",")]
    if not tokens:
        raise ValueError("invalid_header")
    out: set[str] = set()
    for raw in tokens:
        if not _ETAG_TOKEN_RE.match(raw):
            raise ValueError("invalid_header")
        if raw.strip() == "*":
            if not allow_star:
                raise ValueError("invalid_header")
            out.add("*")
            continue
        # normalize and reject empty entity-tag
        n = _normalize_tag(raw)
        if not n:
            raise ValueError("invalid_header")
        out.add(n)
    if not out:
        raise ValueError("invalid_header")
    return out


def invalid_header_problem(name: str) -> Response:
    """Return RFC7807 400 for invalid header values.

    Shape: {type, title, status, detail, invalid_params:[{name, reason:"invalid_header"}]}
    """
    class _InvalidParam(TypedDict):
        name: str
        reason: str

    class BadRequestProblem(TypedDict):
        type: str
        title: str
        status: int
        detail: str
        invalid_params: list[_InvalidParam]

    payload: BadRequestProblem = {
        "type": "about:blank",
        "title": "Bad Request",
        "status": 400,
        "detail": "Invalid header",
        "invalid_params": [{"name": name, "reason": "invalid_header"}],
    }
    resp = jsonify(payload)
    resp.status_code = 400
    resp.headers["Content-Type"] = "application/problem+json"
    return resp


def precondition_failed(
    expected: str | None,
    got: str | None,
    *,
    resource: str = "admin_user",
    resource_id: object | None = None,
) -> Response:
    """Return RFC7807 412 response for failed precondition."""
    class PreconditionFailedProblem(TypedDict, total=False):
        type: str
        title: str
        status: int
        detail: str
        resource: str
        resource_id: NotRequired[str]
        expected_etag: str | None
        got_etag: str | None

    payload: PreconditionFailedProblem = {
        "type": "about:blank",
        "title": "Precondition Failed",
        "status": 412,
        "detail": "If-Match did not match",
        "resource": resource,
    }
    if resource_id is not None:
        payload["resource_id"] = str(resource_id)
    # Always include keys for easier client handling and to satisfy tests
    payload["expected_etag"] = expected
    payload["got_etag"] = got
    resp = jsonify(payload)
    resp.status_code = 412
    resp.headers["Content-Type"] = "application/problem+json"
    return resp
