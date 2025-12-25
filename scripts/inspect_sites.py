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
        try:
            print("DB_URL=", os.getenv("DATABASE_URL") or "sqlite:///dev.db")
            rows = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('sites','tenants','users')")).fetchall()
            print("Tables present:", [r[0] for r in rows])
            def q(sql: str, label: str):
                try:
                    res = db.execute(text(sql)).fetchall()
                    print(label, len(res), res[:5])
                except Exception as e:
                    print(label, "ERR:", e)
            q("SELECT id,name,tenant_id FROM sites ORDER BY name", "sites")
            q("SELECT id,name FROM tenants ORDER BY id DESC", "tenants")
            q("SELECT id,tenant_id,email,role FROM users ORDER BY id DESC", "users")
        finally:
            db.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
