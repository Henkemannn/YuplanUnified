from __future__ import annotations

import os
from core.app_factory import create_app
from whitenoise import WhiteNoise

# Expose a module-level WSGI application for Gunicorn
app = create_app()

# Wrap with WhiteNoise to robustly serve static assets in production
static_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "static"))
app = WhiteNoise(app, root=static_root, prefix="static/")
