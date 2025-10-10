from core import create_app


def test_rate_limit_sets_retry_after():
    app = create_app({"TESTING": True, "SECRET_KEY": "x", "AUTH_RATE_LIMIT": {"window_sec": 300, "max_failures": 3, "lock_sec": 60}})
    client = app.test_client()
    # trigger failures until lock
    for _ in range(3):
        r = client.post("/auth/login", json={"email": "nosuch@example.com", "password": "bad"})
    assert r.status_code == 429, r.get_data(as_text=True)
    assert "Retry-After" in r.headers
    v = r.headers.get("Retry-After")
    assert v.isdigit()
    assert int(v) > 0
