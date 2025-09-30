"""Utility script to set (or create) the primary superuser credentials.

Usage: python scripts/set_superuser.py

NOTE: Contains a plaintext password per explicit user request. Remove or edit after use.
"""
import os, sys
from werkzeug.security import generate_password_hash

# Ensure project root on sys.path when running as standalone script
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.db import get_session
from core.models import User, Tenant
from core.config import Config
from core.db import init_engine

TARGET_EMAIL = "info@yuplan.se"
TARGET_PASSWORD = "G0teb0rg031"  # Plaintext by user instruction

def main():
    cfg = Config.from_env()
    init_engine(cfg.database_url)
    db = get_session()
    try:
        # Ensure at least one tenant exists
        tenant = db.query(Tenant).first()
        if not tenant:
            tenant = Tenant(name="Primary")  # type: ignore
            db.add(tenant)
            db.flush()

        # Try find existing superuser (role == superuser) OR existing by email
        user = db.query(User).filter(User.email == TARGET_EMAIL.lower()).first()
        if not user:
            user = db.query(User).filter(User.role == 'superuser').first()

        if user:
            user.email = TARGET_EMAIL.lower()
            user.password_hash = generate_password_hash(TARGET_PASSWORD)
            user.role = 'superuser'
            user.tenant_id = tenant.id
            action = 'updated'
        else:
            user = User(
                tenant_id=tenant.id,
                email=TARGET_EMAIL.lower(),
                password_hash=generate_password_hash(TARGET_PASSWORD),
                role='superuser',
                unit_id=None
            )
            db.add(user)
            action = 'created'
        db.commit()
        print(f"Superuser {action}: id={user.id} email={user.email}")
    finally:
        db.close()

if __name__ == '__main__':
    main()
