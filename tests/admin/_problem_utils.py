from __future__ import annotations

from typing import Any


def assert_problem(resp, expected_status: int | None = None, expected_title: str | None = None) -> dict[str, Any]:
    """Assert RFC7807 problem+json basics and return parsed body.

    - Ensures Content-Type starts with application/problem+json
    - Ensures body has type, title, status
    - Optionally asserts specific status/title
    """
    if expected_status is not None:
        assert resp.status_code == expected_status
    ctype = resp.headers.get("Content-Type", "")
    assert ctype.startswith("application/problem+json")
    body = resp.get_json()
    assert isinstance(body, dict)
    assert {"type", "title", "status"}.issubset(body.keys())
    # type may be about:blank unless specified otherwise by server
    if expected_status is not None:
        assert body.get("status") == expected_status
    if expected_title is not None:
        assert body.get("title") == expected_title
    return body
