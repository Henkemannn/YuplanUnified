from __future__ import annotations

from core.app_factory import create_app

# Expose a module-level WSGI application for Gunicorn
app = create_app()
