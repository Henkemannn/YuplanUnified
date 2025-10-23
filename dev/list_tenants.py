import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.config import Config
from core.db import get_session, init_engine
from core.models import Tenant

if __name__ == "__main__":
    cfg = Config.from_env()
    init_engine(cfg.database_url)
    s = get_session()
    try:
        rows = s.query(Tenant).order_by(Tenant.id.asc()).all()
        print(f"DB: {cfg.database_url}")
        print(f"tenants: {len(rows)}")
        for t in rows:
            print(f"{t.id}\t{t.name}\t{t.slug}\t{t.created_at}")
    finally:
        s.close()
