"""Utility script to set (or create) the primary superuser credentials.

Usage: python scripts/set_superuser.py

Reads password from environment variable YUPLAN_SUPERUSER_PASSWORD (no hardcoded fallback).
"""
import os
import sys

from werkzeug.security import generate_password_hash

# Ensure project root on sys.path when running as standalone script
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.config import Config
from core.db import get_session, init_engine
from core.models import Tenant, User

TARGET_EMAIL = "info@yuplan.se"
ENV_VAR = "YUPLAN_SUPERUSER_PASSWORD"

def main():
    cfg = Config.from_env()
    init_engine(cfg.database_url)
    db = get_session()
    try:
        password = os.environ.get(ENV_VAR)
        if not password:
            sys.stderr.write(
                f"[ERROR] Missing env var {ENV_VAR}. Set it securely and retry.\n"
            )
            sys.exit(1)
        # Ensure at least one tenant exists
        tenant = db.query(Tenant).first()
        if not tenant:
            tenant = Tenant(name="Primary")
            db.add(tenant)
            db.flush()

        # Try find existing superuser (role == superuser) OR existing by email
        user = db.query(User).filter(User.email == TARGET_EMAIL.lower()).first()
        if not user:
            user = db.query(User).filter(User.role == "superuser").first()

        if user:
            user.email = TARGET_EMAIL.lower()
            user.password_hash = generate_password_hash(password)
            user.role = "superuser"
            user.tenant_id = tenant.id
            action = "updated"
        else:
            user = User(
                tenant_id=tenant.id,
                email=TARGET_EMAIL.lower(),
                password_hash=generate_password_hash(password),
                role="superuser",
                unit_id=None
            )
            db.add(user)
            action = "created"
        db.commit()
        print(f"Superuser {action}: id={user.id} email={user.email}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
