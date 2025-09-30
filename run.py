"""Development runner.
Usage: python run.py  (reads .env if present)
Set DEV_CREATE_ALL=1 to auto-create tables (development only).
"""
from __future__ import annotations
import os
from core import create_app  # type: ignore
from dotenv import load_dotenv

load_dotenv()

app = create_app()

if __name__ == "__main__":  # pragma: no cover
    app.run(debug=True)
