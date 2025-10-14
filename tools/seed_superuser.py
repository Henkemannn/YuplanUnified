from __future__ import annotations

import argparse
import sys

from werkzeug.security import generate_password_hash

try:
    from core import create_app
    from core.db import create_all, get_session
    from core.models import Tenant, User
except Exception as e:  # pragma: no cover
    print("Import error:", e)
    sys.exit(1)


def main() -> int:
    p = argparse.ArgumentParser(description="Create or update a superuser for local dev")
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    args = p.parse_args()

    app = create_app()
    with app.app_context():
        db = get_session()
        try:
            # Show DB URI/path for diagnostics
            try:
                uri = str(db.bind.url)  # type: ignore[attr-defined]
            except Exception:
                uri = app.config.get("SQLALCHEMY_DATABASE_URI", "<unknown>")
            print("DB:", uri)
            # Ensure tables
            try:
                create_all()
            except Exception:
                pass

            # Ensure tenant exists
            tenant = db.query(Tenant).first()
            if not tenant:
                tenant = Tenant(name="Primary")
                db.add(tenant)
                db.flush()

            # Create or update user
            user = db.query(User).filter(User.email == args.email.lower()).first()
            if not user:
                user = User(
                    tenant_id=tenant.id,
                    email=args.email.lower(),
                    password_hash=generate_password_hash(args.password),
                    role="superuser",
                    unit_id=None,
                )
                db.add(user)
            else:
                user.password_hash = generate_password_hash(args.password)
                user.role = "superuser"
            db.commit()
            print(f"Superuser ready: {args.email}")
            return 0
        finally:
            db.close()


if __name__ == "__main__":
    raise SystemExit(main())
