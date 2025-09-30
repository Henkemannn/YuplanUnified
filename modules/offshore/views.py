from __future__ import annotations

from flask import Blueprint

bp = Blueprint("offshore", __name__, url_prefix="/offshore")

@bp.get("/ping")
def ping():  # pragma: no cover
    return {"module": "offshore", "ok": True}
