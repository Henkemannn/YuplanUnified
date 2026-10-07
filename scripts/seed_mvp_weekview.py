"""Seed the Kommun MVP Weekview pilot flag.

This keeps the pilot state reproducible by persisting the canonical tenant-scoped
feature flag for tenant 2 instead of relying on environment defaults.
"""
from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import text

# Ensure project root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.app_factory import create_app  # noqa: E402
from core.feature_service import FeatureService  # noqa: E402
from core.db import create_all, get_session  # noqa: E402


DEFAULT_TENANT_ID = 2
DEFAULT_TENANT_NAME = "MVP Test1"
FLAG_NAME = "ff.weekview.enabled"


def ensure_pilot_weekview_enabled(*, tenant_id: int = DEFAULT_TENANT_ID, tenant_name: str = DEFAULT_TENANT_NAME) -> None:
    db = get_session()
    try:
        db.execute(
            text(
                "INSERT INTO tenants(id, name, active) VALUES(:id, :name, 1) "
                "ON CONFLICT(id) DO UPDATE SET active=1"
            ),
            {"id": int(tenant_id), "name": tenant_name},
        )
        db.commit()
    finally:
        db.close()
    FeatureService().enable(int(tenant_id), FLAG_NAME)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the Kommun MVP Weekview pilot flag (dev-only)")
    parser.add_argument("--tenant-id", type=int, default=DEFAULT_TENANT_ID)
    parser.add_argument("--tenant-name", default=DEFAULT_TENANT_NAME)
    args = parser.parse_args()

    app = create_app({"TESTING": False, "SECRET_KEY": "dev"})
    with app.app_context():
        create_all()
        ensure_pilot_weekview_enabled(tenant_id=args.tenant_id, tenant_name=args.tenant_name)

    print(f"Seeded {FLAG_NAME}=ON for tenant {args.tenant_id} ({args.tenant_name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())