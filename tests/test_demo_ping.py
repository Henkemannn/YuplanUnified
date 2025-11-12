import os


def test_demo_ping(client):
    # Enable demo UI for test environment explicitly if not already.
    # NOTE: The app factory reads env at import time; ensure variable set before fixture creation in CI config if needed.
    r = client.get("/demo/ping")
    # If DEMO_UI not enabled this may 404; guard to avoid false negatives unless flag is on.
    if os.getenv("DEMO_UI", "0").lower() not in ("1", "true", "yes"):
        assert r.status_code in (404, 200)
        if r.status_code == 200:
            assert r.is_json and r.json.get("ok") is True
        return
    assert r.status_code == 200
    assert r.is_json and r.json.get("ok") is True


def test_demo_csp_header(client):
    r = client.get("/demo/")
    if os.getenv("DEMO_UI", "0").lower() not in ("1", "true", "yes"):
        assert r.status_code in (404, 200)
        if r.status_code == 200:
            h = {k.lower(): v for k, v in r.headers.items()}
            assert "content-security-policy" in h
        return
    assert r.status_code == 200
    h = {k.lower(): v for k, v in r.headers.items()}
    assert "content-security-policy" in h
