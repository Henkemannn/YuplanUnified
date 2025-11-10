from __future__ import annotations

import os
import sys
from typing import NoReturn

from alembic import command
from alembic.config import Config as AlembicConfig

# Ensure project root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from core.db import init_engine, get_session  # noqa: E402
from core.models import Tenant, Unit  # noqa: E402


def run_migrations(database_url: str) -> None:
    alembic_ini = os.path.join(ROOT, "alembic.ini")
    acfg = AlembicConfig(alembic_ini)
    # Pass URL via env override supported by migrations/env.py
    os.environ.setdefault("DATABASE_URL", database_url)
    # Use 'heads' to support multiple Alembic branches being upgraded
    command.upgrade(acfg, "heads")


def seed_minimal() -> None:
    """Create one tenant and two units if not present."""
    db = get_session()
    try:
        tenant = db.query(Tenant).filter(Tenant.name == "demo").first()
        if not tenant:
            tenant = Tenant(name="demo", active=True)
            db.add(tenant)
            db.flush()
        # Two units
        existing = {u.name for u in db.query(Unit).filter(Unit.tenant_id == tenant.id).all()}
        for nm in ("Alpha", "Bravo"):
            if nm not in existing:
                db.add(Unit(tenant_id=tenant.id, name=nm, default_attendance=None))
        db.commit()
        print(f"Seeded tenant id={tenant.id} with units Alpha, Bravo")
    finally:
        db.close()


def main() -> NoReturn:
    url = os.environ.get("DATABASE_URL", "sqlite:///unified.db")
    print(f"Using DATABASE_URL={url}")
    # Initialize engine for ORM seed steps
    init_engine(url, force=True)
    run_migrations(url)
    seed_minimal()
    print("Done.")
    raise SystemExit(0)


if __name__ == "__main__":
    main()
