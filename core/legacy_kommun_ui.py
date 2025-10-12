"""Legacy Kommun UI adapter.

First target: expose /kommun/admin (adminpanel) using unified models:
 - Units -> avdelningar
 - DietaryType -> kosttyper
 - UnitDietAssignment -> kopplingar

Write-only adapter: initial version is READ-ONLY (no POST persistence yet) to avoid
immediate schema coupling. We will progressively enable actions mapped to unified services.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from email.utils import formatdate

from flask import Blueprint, Response, redirect, render_template, request, session, url_for

from .auth import require_roles
from .db import get_session
from .models import DietaryType, Unit, UnitDietAssignment

bp = Blueprint(
    "legacy_kommun_ui",
    __name__,
    url_prefix="/kommun",
    template_folder="../legacy/kommun/templates",
    static_folder="../legacy/kommun/static",
)


# --- Shared lightweight HTTP caching helpers (ETag + optional Last-Modified) ---
def _etag_headers(
    etag_hex: str, *, last_modified_dt: datetime | None = None, vary_accept: bool = False
):
    headers = {
        "ETag": f'"{etag_hex}"',  # quoted per RFC 7232
        "Cache-Control": "private, max-age=60, must-revalidate",
        "Vary": "Accept-Encoding" + (", Accept" if vary_accept else ""),
    }
    if last_modified_dt is not None:
        headers["Last-Modified"] = formatdate(last_modified_dt.timestamp(), usegmt=True)
    return headers


def _if_none_match_matches(etag_hex: str) -> bool:
    inm = request.headers.get("If-None-Match")
    return inm is not None and inm.strip() == f'"{etag_hex}"'


class AvdRow:
    __slots__ = ("id", "namn", "boende_antal", "kopplade_kosttyper", "kopplade_antal", "faktaruta")

    def __init__(self, u: Unit):
        self.id = u.id
        self.namn = u.name
        self.boende_antal = u.default_attendance or 0
        self.kopplade_kosttyper = set()
        self.kopplade_antal = {}
        self.faktaruta = ""


def _unit_row(u: Unit):
    return AvdRow(u)


def _diet_row(d: DietaryType):
    return type("Kost", (), {"id": d.id, "namn": d.name, "formarkeras": d.default_select})()


@bp.route("/admin")
@require_roles("superuser", "admin")
def adminpanel():
    tenant_id = session.get("tenant_id")
    if not tenant_id:
        return redirect(url_for("demo.login"))  # fallback
    vecka = int(date.today().strftime("%W")) or 1
    db = get_session()
    try:
        units = db.query(Unit).filter(Unit.tenant_id == tenant_id).all()
        diets = db.query(DietaryType).filter(DietaryType.tenant_id == tenant_id).all()
        assigns = db.query(UnitDietAssignment).all()
    finally:
        db.close()
    # Build mapping for kosttyper kopplingar
    unit_map: dict[int, AvdRow] = {u.id: _unit_row(u) for u in units}
    for a in assigns:
        if a.unit_id in unit_map:
            unit_map[a.unit_id].kopplade_kosttyper.add(a.dietary_type_id)
            unit_map[a.unit_id].kopplade_antal[a.dietary_type_id] = a.count
    avdelningar = list(unit_map.values())
    kosttyper = [_diet_row(d) for d in diets]
    # Template expects a bunch of context names; supply minimal
    return render_template(
        "adminpanel.html",
        valt_vecka=vecka,
        avdelningar=avdelningar,
        kosttyper=kosttyper,
        # The full template has conditional sections; we feed placeholders
        meny_alt1={},
        meny_alt2={},
        meny_dessert={},
        meny_kvall={},
        meny_text_map={},
    )


@bp.route("/admin/import", methods=["GET", "POST"])
@require_roles("superuser", "admin", "cook")
def admin_import():
    # Simple page that posts to unified import endpoint
    html = """
        <div class='container'>
            <h1>Importera meny</h1>
            <form method='post' action='/import/menu' enctype='multipart/form-data'>
                <input type='file' name='file' required>
                <button class='btn btn-primary mt-2'>Ladda upp</button>
            </form>
            <p class='mt-3 text-muted'>DOCX (kommun) eller XLSX (offshore). Tenant hämtas från session.</p>
        </div>
        """
    return render_template("base.html", content=html)


# --- Placeholder routes referenced by templates (to be implemented properly later) ---


@bp.route("/meny_avdelning_admin")
@require_roles("superuser", "admin")
def meny_avdelning_admin():
    # TODO: implement detailed per-unit menu editing view
    return redirect(url_for("legacy_kommun_ui.adminpanel"))


# Alias endpoints (legacy templates call url_for('meny_avdelning_admin'))
bp.add_url_rule(
    "/meny_avdelning_admin_alias", endpoint="meny_avdelning_admin", view_func=meny_avdelning_admin
)


@bp.route("/veckovy")
@require_roles("superuser", "admin")
def veckovy():
    # Placeholder implementation now returns a trivial HTML snippet to enable caching semantics.
    vecka = int(date.today().strftime("%W")) or 1
    avdelning = "all"
    # The legacy template calls url_for('veckovy', ...); to remain compatible, add
    # a transient endpoint alias if not already present.
    if "veckovy" not in bp.deferred_functions:  # not a robust check but avoids duplicates
        try:  # pragma: no cover - defensive
            bp.add_url_rule("/veckovy_alias", endpoint="veckovy", view_func=veckovy)  # type: ignore
        except Exception:
            pass
    # Minimal HTML to avoid deep legacy template dependencies (which expect un-namespaced endpoint names)
    html = f"""<html><head><title>Veckovy {vecka}</title></head>
    <body><h1>Veckovy vecka {vecka}</h1><p>Avdelning: {avdelning}</p></body></html>"""
    body_bytes = html.encode("utf-8")
    etag_hex = hashlib.sha256(
        b"veckovy:" + str(vecka).encode() + b":" + str(avdelning).encode() + b":" + body_bytes
    ).hexdigest()
    if _if_none_match_matches(etag_hex):
        return Response(status=304, headers=_etag_headers(etag_hex, vary_accept=True))
    resp = Response(body_bytes, mimetype="text/html; charset=utf-8")
    for k, v in _etag_headers(etag_hex, vary_accept=True).items():
        resp.headers[k] = v
    return resp


@bp.route("/rapport", methods=["GET", "POST"])
@require_roles("superuser", "admin")
def rapport():
    # Placeholder JSON report payload to enable ETag caching. Replace rapport_data collection later.
    vecka = int(date.today().strftime("%W")) or 1
    avdelning = "all"
    rapport_data = {"summary": "placeholder", "rows": []}
    payload = {"vecka": vecka, "avdelning": avdelning, "data": rapport_data}
    body_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    etag_hex = hashlib.sha256(
        b"rapport:" + str(vecka).encode() + b":" + str(avdelning).encode() + b":" + body_bytes
    ).hexdigest()
    if _if_none_match_matches(etag_hex):
        return Response(status=304, headers=_etag_headers(etag_hex))
    resp = Response(body_bytes, mimetype="application/json")
    for k, v in _etag_headers(etag_hex).items():
        resp.headers[k] = v
    return resp


@bp.route("/redigera_boende")
@require_roles("superuser", "admin")
def redigera_boende():
    # TODO: implement editing of per-day attendance (maps to Attendance model)
    return redirect(url_for("legacy_kommun_ui.adminpanel"))
