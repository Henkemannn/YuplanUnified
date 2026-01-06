from __future__ import annotations
import os, sys
sys.path.append(os.getcwd())
from sqlalchemy import text
from core import create_app
from core.db import get_session


def main() -> int:
    app = create_app({"TESTING": True})
    with app.app_context():
        db = get_session()
        created = 0
        try:
            # Ensure sites table exists with tenant_id
            db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT, version INTEGER, tenant_id INTEGER)"))
            try:
                db.execute(text("ALTER TABLE sites ADD COLUMN tenant_id INTEGER"))
            except Exception:
                pass
            # Find tenants without a site
            tenant_rows = db.execute(text("SELECT id, name FROM tenants ORDER BY id"))
            tenants = [(int(r[0]), str(r[1] or "")) for r in tenant_rows.fetchall()]
            site_rows = db.execute(text("SELECT DISTINCT tenant_id FROM sites WHERE tenant_id IS NOT NULL"))
            has_site = {int(r[0]) for r in site_rows.fetchall() if r[0] is not None}
            for tid, tname in tenants:
                if tid in has_site:
                    continue
                # Skip special primary/superuser tenant if desired
                if tname.lower() in ("primary",):
                    continue
                # Create a default site named same as tenant
                slug = tname.lower().strip().replace(" ", "-") or f"site-{tid}"
                db.execute(text("INSERT OR REPLACE INTO sites(id,name,version,tenant_id) VALUES(:id,:name,0,:tenant_id)"),
                           {"id": slug, "name": tname, "tenant_id": tid})
                created += 1
            db.commit()
            print(f"Backfill complete. Created {created} site(s).")
        finally:
            db.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
