"""Development runner.
Usage: python run.py  (reads .env if present)
Set DEV_CREATE_ALL=1 to auto-create tables (development only).
"""
from __future__ import annotations

from dotenv import load_dotenv

from core import create_app  # type: ignore

load_dotenv()

app = create_app()

if __name__ == "__main__":  # pragma: no cover
    app.run(debug=True)
