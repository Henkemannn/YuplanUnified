from __future__ import annotations

from datetime import datetime

from core.concurrency import parse_if_match, precondition_failed, user_etag


def test_parse_if_match_multiple_and_weak_and_star_and_invalid():
    # multiple, weak, and duplicates normalize and dedupe
    assert parse_if_match('W/"abc", "def", W/"abc"') == {"abc", "def"}
    # star preserved
    assert "*" in parse_if_match("*")
    # invalid tokens are included as-is (no strict validation here)
    tags = parse_if_match(' , , invalid, "noend')
    assert "invalid" in tags
    assert '"noend' in tags
    # empty/None -> empty set
    assert parse_if_match("") == set()
    assert parse_if_match(None) == set()


def test_user_etag_stable_and_format():
    # stable across calls with same inputs
    dt = datetime(2025, 1, 1, 12, 0, 0)
    e1 = user_etag(42, dt)
    e2 = user_etag(42, dt)
    assert e1 == e2
    assert isinstance(e1, str) and e1.startswith('W/"') and e1.endswith('"')

    # when updated_at is None, hash uses empty timestamp portion
    e3 = user_etag(42, None)
    assert isinstance(e3, str) and e3.startswith('W/"') and e3.endswith('"')
    assert e3 != "" and e3 != e1  # typically different from when timestamp is present


def test_precondition_failed_includes_expected_and_got(client_admin):
    # Use application context to allow jsonify to work
    app = client_admin.application
    with app.app_context():
        resp = precondition_failed('W/"abc"', None)
        assert resp.status_code == 412
        assert resp.headers.get("Content-Type") == "application/problem+json"
        body = resp.get_json()
        assert body.get("expected_etag") == 'W/"abc"'
        assert "got_etag" in body
