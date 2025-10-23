from __future__ import annotations

import json
import os
import sys
from typing import Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import uuid

from core.app_factory import create_app


def pretty(d: Any) -> str:
    try:
        return json.dumps(d, ensure_ascii=False, indent=2)
    except Exception:
        return str(d)


def run() -> int:
    app = create_app({
        "TESTING": True,
        # Disable strict CSRF in test client context
        "YUPLAN_STRICT_CSRF": False,
    })

    results = []
    with app.test_client() as c:
        hdr = {
            "X-User-Role": "superuser",
            # Simulate a user id as app_factory will assign session if present
            "X-User-Id": "1",
        }
        # Health (superuser API)
        rv = c.get("/api/superuser/health", headers=hdr)
        results.append(("health", rv.status_code, rv.json))

        # Create unique tenant (happy path)
        base = f"test-{uuid.uuid4().hex[:8]}"
        name1 = f"Test Kommun {base}"
        slug1 = base
        payload = {"name": name1, "slug": slug1, "theme": "ocean", "enabled": True}
        rv = c.post("/api/superuser/tenants", headers={**hdr, "Content-Type": "application/json"}, data=json.dumps(payload))
        results.append(("create_ok", rv.status_code, rv.json))

        # Duplicate name -> 400
        payload2 = {"name": name1, "slug": f"{slug1}-x", "theme": "ocean", "enabled": True}
        rv = c.post("/api/superuser/tenants", headers={**hdr, "Content-Type": "application/json"}, data=json.dumps(payload2))
        results.append(("dup_name", rv.status_code, rv.json))

        # Duplicate slug -> 400
        payload3 = {"name": f"Another {base}", "slug": slug1, "theme": "ocean", "enabled": True}
        rv = c.post("/api/superuser/tenants", headers={**hdr, "Content-Type": "application/json"}, data=json.dumps(payload3))
        results.append(("dup_slug", rv.status_code, rv.json))

        # Invalid theme -> 400
        payload4 = {"name": "Bad Theme", "slug": "bad-theme", "theme": "purple", "enabled": True}
        rv = c.post("/api/superuser/tenants", headers={**hdr, "Content-Type": "application/json"}, data=json.dumps(payload4))
        results.append(("bad_theme", rv.status_code, rv.json))

    # Print compact summary for terminal
    print("\nValidation results:")
    for name, code, body in results:
        print(f"- {name}: {code}")
        print(pretty(body))
    # Basic success criteria: first is 200, create is 201, dup_name 400, dup_slug 400, bad_theme 400
    ok = (
        results[0][1] == 200 and
        results[1][1] == 201 and
        results[2][1] == 400 and
        results[3][1] == 400 and
        results[4][1] == 400
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(run())
