from __future__ import annotations

import argparse
import sys

from werkzeug.security import check_password_hash

try:
    from core import create_app
    from core.db import get_session
    from core.models import User
except Exception as e:  # pragma: no cover
    print("Import error:", e)
    sys.exit(1)


def main() -> int:
    p = argparse.ArgumentParser(description="Check if a user exists and validate password")
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    args = p.parse_args()

    app = create_app()
    with app.app_context():
        db = get_session()
        try:
            # Show DB URI/path
            try:
                uri = str(db.bind.url)  # type: ignore[attr-defined]
            except Exception:
                uri = app.config.get("SQLALCHEMY_DATABASE_URI", "<unknown>")
            print("DB:", uri)

            user = db.query(User).filter(User.email == args.email.lower()).first()
            if not user:
                print("User not found")
                return 2
            ok = False
            try:
                ok = check_password_hash(user.password_hash, args.password)
            except Exception:
                pass
            print("User id:", user.id, "role:", user.role)
            print("Password match:", ok)
            return 0 if ok else 1
        finally:
            db.close()


if __name__ == "__main__":
    raise SystemExit(main())
