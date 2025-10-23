from __future__ import annotations

import argparse

from core import create_app


def main() -> int:
    p = argparse.ArgumentParser(description="Smoke test /tasks/ access after login")
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    args = p.parse_args()

    app = create_app({"TESTING": True})
    client = app.test_client()

    r = client.post("/auth/login", json={"email": args.email, "password": args.password})
    if r.status_code != 200:
        print("login failed:", r.status_code, r.get_json())
        return 1
    resp = client.get("/tasks/")
    try:
        data = resp.get_json() or {}
    except Exception:
        data = {"raw": resp.data.decode("utf-8", "ignore")}
    print("/tasks/ status:", resp.status_code)
    print("/tasks/ body keys:", list(data.keys()) if isinstance(data, dict) else type(data))
    return 0 if resp.status_code == 200 else 2


if __name__ == "__main__":
    raise SystemExit(main())
