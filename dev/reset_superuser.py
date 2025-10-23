"""Reset or create the bootstrap superuser using env SUPERUSER_EMAIL/SUPERUSER_PASSWORD.

Usage (from repo root):
  python dev/reset_superuser.py

Loads .env, creates app context, and calls ensure_bootstrap_superuser().
"""
from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from core import create_app  # noqa: E402
from core.auth import ensure_bootstrap_superuser  # noqa: E402


def main() -> int:
    app = create_app()
    with app.app_context():
        ensure_bootstrap_superuser()
    print("Bootstrap superuser ensured from env.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
