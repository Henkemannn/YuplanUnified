from __future__ import annotations

import argparse
import sys

from core import create_app


def main() -> int:
    p = argparse.ArgumentParser(description="Smoke test /auth/login using Flask test client")
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    args = p.parse_args()

    app = create_app({"TESTING": True})
    client = app.test_client()

    resp = client.post(
        "/auth/login",
        json={"email": args.email, "password": args.password},
    )
    try:
        data = resp.get_json() or {}
    except Exception:
        data = {"raw": resp.data.decode("utf-8", "ignore")}
    print("/auth/login status:", resp.status_code)
    print("/auth/login body:", data)

    if resp.status_code != 200 or not isinstance(data, dict) or not data.get("ok"):
        return 1

    # Verify session cookie by calling /auth/me with the same client (cookies persist)
    me = client.get("/auth/me")
    try:
        me_data = me.get_json() or {}
    except Exception:
        me_data = {"raw": me.data.decode("utf-8", "ignore")}
    print("/auth/me status:", me.status_code)
    print("/auth/me body:", me_data)

    return 0 if me.status_code == 200 and me_data.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
