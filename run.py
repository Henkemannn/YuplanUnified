"""Development runner.
Usage: python run.py  (reads .env if present)
Set DEV_CREATE_ALL=1 to auto-create tables (development only).
"""

from __future__ import annotations

from pathlib import Path
import os

from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path, override=False)
secret_value = os.getenv("SECRET_KEY") or ""
secret_prefix = secret_value[:6]
print(
    f"DOTENV: path={env_path} exists={env_path.exists()} SECRET_KEY_len={len(secret_value)} prefix={secret_prefix}",
    flush=True,
)

import argparse
import inspect
import secrets

from sqlalchemy import text
from werkzeug.security import generate_password_hash

from core.app_factory import create_app
from core.db import get_session, init_engine
from core.models import Tenant, User


def _sqlite_db_path(db_url: str | None) -> str | None:
    if not db_url:
        return None
    if db_url == "sqlite:///:memory:":
        return None
    if db_url.startswith("sqlite:///"):
        raw_path = db_url.replace("sqlite:///", "", 1)
        return os.path.abspath(raw_path)
    return None


def _db_path_stats(db_url: str | None) -> tuple[str, bool, int]:
    sqlite_path = _sqlite_db_path(db_url)
    if not sqlite_path:
        return "N/A", False, 0
    exists = os.path.exists(sqlite_path)
    size = os.path.getsize(sqlite_path) if exists else 0
    return sqlite_path, exists, size


def _table_exists(db, table: str) -> bool:
    try:
        engine = getattr(db, "bind", db)
        if engine.dialect.name == "sqlite":
            row = db.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
                {"t": table},
            ).fetchone()
            return bool(row)
        row = db.execute(
            text("SELECT 1 FROM information_schema.tables WHERE table_name = :t"),
            {"t": table},
        ).fetchone()
        return bool(row)
    except Exception:
        return False


def _count_rows(db, table: str) -> tuple[int, bool]:
    if not _table_exists(db, table):
        return 0, True
    try:
        row = db.execute(text(f"SELECT COUNT(*) FROM {table}")).fetchone()
        return int(row[0] or 0), False
    except Exception:
        return 0, True


def _ensure_tenant(db) -> Tenant:
    tenant = db.query(Tenant).first()
    if not tenant:
        tenant = Tenant(name="Primary")
        db.add(tenant)
        db.flush()
    return tenant


def _generate_temp_password() -> str:
    return secrets.token_urlsafe(12)


def _dev_user_log(action: str) -> None:
    try:
        env_val = (os.getenv("APP_ENV") or os.getenv("FLASK_ENV") or "").lower()
        if env_val != "dev" and env_val != "development" and os.getenv("YUPLAN_DEV_HELPERS", "0").lower() not in ("1", "true", "yes"):
            return
        frame = inspect.currentframe()
        caller = frame.f_back if frame else None
        func = caller.f_code.co_name if caller else "unknown"
        line = caller.f_lineno if caller else 0
        print(f"DEV_USER_MUTATION action={action} func={func} file={__file__} line={line}")
    except Exception:
        pass


def dev_repair_menu_tenant() -> int:
    env_val = (os.getenv("APP_ENV") or os.getenv("FLASK_ENV") or "").lower()
    if env_val not in ("dev", "development"):
        print("DEV REPAIR: skipped (not in development)")
        return 1
    app = create_app()
    with app.app_context():
        db_url = app.config.get("SQLALCHEMY_DATABASE_URI")
        if db_url:
            init_engine(db_url, force=True)
        db = get_session()
        try:
            res = db.execute(
                text(
                    """
                    UPDATE menus
                    SET tenant_id = (SELECT tenant_id FROM sites WHERE sites.id = menus.site_id)
                    WHERE site_id IS NOT NULL
                      AND tenant_id != (SELECT tenant_id FROM sites WHERE sites.id = menus.site_id)
                    """
                )
            )
            db.commit()
            count = int(res.rowcount or 0)
            print(f"DEV REPAIR: fixed {count} menu rows tenant_id")
            return 0
        finally:
            db.close()


def auth_doctor() -> int:
    app = create_app()
    with app.app_context():
        db_url = app.config.get("SQLALCHEMY_DATABASE_URI")
        db_path, exists, size = _db_path_stats(db_url)
        print(f"DB_PATH: {db_path}")
        print(f"EXISTS: {exists}")
        print(f"SIZE_BYTES: {size}")

        if db_url:
            init_engine(db_url, force=True)
        db = get_session()
        try:
            users_count, users_missing = _count_rows(db, "users")
            tenants_count, tenants_missing = _count_rows(db, "tenants")
            sites_count, sites_missing = _count_rows(db, "sites")

            users_note = " (table missing)" if users_missing else ""
            tenants_note = " (table missing)" if tenants_missing else ""
            sites_note = " (table missing)" if sites_missing else ""

            print(f"users: {users_count}{users_note}")
            print(f"tenants: {tenants_count}{tenants_note}")
            print(f"sites: {sites_count}{sites_note}")

            superuser_exists = False
            if not users_missing:
                row = db.execute(
                    text("SELECT 1 FROM users WHERE role = :r LIMIT 1"),
                    {"r": "superuser"},
                ).fetchone()
                superuser_exists = bool(row)
            print(f"superuser_exists: {superuser_exists}")
        finally:
            db.close()
    return 0


def auth_reset(email: str, role: str, password: str | None, password_env: str | None) -> int:
    role = role.strip().lower()
    if role not in {"superuser", "admin", "cook"}:
        print("ERROR: role must be one of: superuser, admin, cook")
        return 2

    if bool(password) == bool(password_env):
        print("ERROR: provide exactly one of --password or --password-env")
        return 2

    if password_env:
        password = os.environ.get(password_env) or ""
        if not password:
            print("ERROR: password environment variable is missing or empty")
            return 2

    app = create_app()
    with app.app_context():
        db_url = app.config.get("SQLALCHEMY_DATABASE_URI")
        if db_url:
            init_engine(db_url, force=True)
        db = get_session()
        try:
            if not _table_exists(db, "users") or not _table_exists(db, "tenants"):
                print("ERROR: users/tenants tables are missing. Run migrations or set DEV_CREATE_ALL=1 and start the app once.")
                return 1

            tenant = _ensure_tenant(db)
            normalized = email.strip().lower()
            pw_hash = generate_password_hash(password)

            user = db.query(User).filter(User.email == normalized).first()
            if not user:
                _dev_user_log("insert_user")
                user = User(
                    tenant_id=tenant.id,
                    email=normalized,
                    username=normalized,
                    password_hash=pw_hash,
                    role=role,
                    full_name=None,
                    is_active=True,
                    unit_id=None,
                )
                db.add(user)
            else:
                _dev_user_log("update_user_password")
                user.password_hash = pw_hash
                user.role = role
                if not user.username:
                    user.username = normalized
                try:
                    user.is_active = True
                except Exception:
                    pass
                if not user.tenant_id:
                    user.tenant_id = tenant.id

            db.commit()
            print(f"User ready: {normalized} (role={role})")
            print("Password updated.")
            return 0
        finally:
            db.close()


def auth_ensure_superuser() -> int:
    email = os.getenv("SUPERUSER_EMAIL")
    password = os.getenv("SUPERUSER_PASSWORD")
    if not email or not password:
        print("Set SUPERUSER_EMAIL and SUPERUSER_PASSWORD in the environment.")
        print("Then run: python run.py auth-ensure-superuser")
        return 0

    app = create_app()
    with app.app_context():
        db_url = app.config.get("SQLALCHEMY_DATABASE_URI")
        if db_url:
            init_engine(db_url, force=True)
        db = get_session()
        try:
            if not _table_exists(db, "users") or not _table_exists(db, "tenants"):
                print("ERROR: users/tenants tables are missing. Run migrations or set DEV_CREATE_ALL=1 and start the app once.")
                return 1

            tenant = _ensure_tenant(db)
            normalized = email.strip().lower()
            pw_hash = generate_password_hash(password)

            user = db.query(User).filter(User.email == normalized).first()
            if not user:
                _dev_user_log("insert_user")
                user = User(
                    tenant_id=tenant.id,
                    email=normalized,
                    username=normalized,
                    password_hash=pw_hash,
                    role="superuser",
                    full_name=None,
                    is_active=True,
                    unit_id=None,
                )
                db.add(user)
            else:
                _dev_user_log("update_user_password")
                user.password_hash = pw_hash
                user.role = "superuser"
                if not user.username:
                    user.username = normalized
                try:
                    user.is_active = True
                except Exception:
                    pass
                if not user.tenant_id:
                    user.tenant_id = tenant.id

            db.commit()
            print(f"Superuser ensured: {normalized}")
            return 0
        finally:
            db.close()


def auth_reset_superuser_env() -> int:
    email = os.getenv("SUPERUSER_EMAIL")
    password = os.getenv("SUPERUSER_PASSWORD")
    if not email or not password:
        print("Set SUPERUSER_EMAIL and SUPERUSER_PASSWORD in the environment.")
        print("Then run: python run.py auth-reset-superuser")
        return 2

    app = create_app()
    with app.app_context():
        db_url = app.config.get("SQLALCHEMY_DATABASE_URI")
        if db_url:
            init_engine(db_url, force=True)
        db = get_session()
        try:
            if not _table_exists(db, "users"):
                print("ERROR: users table is missing. Run migrations or start the app once.")
                return 1

            normalized = email.strip().lower()
            user = db.query(User).filter(User.email == normalized).first()
            if not user:
                print(f"ERROR: superuser not found for {normalized}")
                return 1

            _dev_user_log("update_user_password")
            user.password_hash = generate_password_hash(password)
            db.commit()
            print(f"AUTH RESET: superuser password updated for {normalized}")
            return 0
        finally:
            db.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dev runner and auth utilities")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("auth-doctor", help="Diagnose auth DB state")

    reset = sub.add_parser("auth-reset", help="Create or reset a user with a specified password")
    reset.add_argument("--email", required=True, help="User email")
    reset.add_argument("--role", default="superuser", help="superuser|admin|cook")
    reset.add_argument("--password", help="Explicit password to set")
    reset.add_argument("--password-env", help="Environment variable containing the password")

    sub.add_parser("auth-ensure-superuser", help="Ensure SUPERUSER_EMAIL/PASSWORD exists in DB")
    sub.add_parser("auth-reset-superuser", help="Reset existing SUPERUSER_EMAIL password from env")
    sub.add_parser("dev-repair-menu-tenant", help="DEV: fix menus.tenant_id to match sites.tenant_id")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "auth-doctor":
        return auth_doctor()
    if args.command == "auth-reset":
        return auth_reset(args.email, args.role, args.password, args.password_env)
    if args.command == "auth-ensure-superuser":
        return auth_ensure_superuser()
    if args.command == "auth-reset-superuser":
        return auth_reset_superuser_env()
    if args.command == "dev-repair-menu-tenant":
        return dev_repair_menu_tenant()

    app = create_app()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    app.run(debug=True, host=host, port=port)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
