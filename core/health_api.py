from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify

bp = Blueprint("health_api", __name__)


@bp.get("/healthz")
def healthz() -> tuple[dict[str, Any], int]:
    # Minimal health endpoint for container orchestrators
    return {"status": "ok"}, 200
