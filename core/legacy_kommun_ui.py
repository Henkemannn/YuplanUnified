"""Legacy Kommun UI adapter.

First target: expose /kommun/admin (adminpanel) using unified models:
 - Units -> avdelningar
 - DietaryType -> kosttyper
 - UnitDietAssignment -> kopplingar

Write-only adapter: initial version is READ-ONLY (no POST persistence yet) to avoid
immediate schema coupling. We will progressively enable actions mapped to unified services.
"""
from __future__ import annotations

from datetime import date

from flask import Blueprint, redirect, render_template, session, url_for

from .auth import require_roles
from .db import get_session
from .models import DietaryType, Unit, UnitDietAssignment

bp = Blueprint(
    "legacy_kommun_ui",
    __name__,
    url_prefix="/kommun",
    template_folder="../legacy/kommun/templates",
    static_folder="../legacy/kommun/static"
)

class AvdRow:
    __slots__ = ("id","namn","boende_antal","kopplade_kosttyper","kopplade_antal","faktaruta")
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
    return type("Kost", (), {
        "id": d.id,
        "namn": d.name,
        "formarkeras": d.default_select
    })()

@bp.route("/admin")
@require_roles("superuser","admin")
def adminpanel():
    tenant_id = session.get("tenant_id")
    if not tenant_id:
        return redirect(url_for("demo.login"))  # fallback
    vecka = int(date.today().strftime("%W")) or 1
    db = get_session()
    try:
        units = db.query(Unit).filter(Unit.tenant_id==tenant_id).all()
        diets = db.query(DietaryType).filter(DietaryType.tenant_id==tenant_id).all()
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
        meny_alt1={}, meny_alt2={}, meny_dessert={}, meny_kvall={}, meny_text_map={},
    )

@bp.route("/admin/import", methods=["GET","POST"])
@require_roles("superuser","admin","cook")
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
@require_roles("superuser","admin")
def meny_avdelning_admin():
    # TODO: implement detailed per-unit menu editing view
    return redirect(url_for("legacy_kommun_ui.adminpanel"))

# Alias endpoints (legacy templates call url_for('meny_avdelning_admin'))
bp.add_url_rule("/meny_avdelning_admin_alias", endpoint="meny_avdelning_admin", view_func=meny_avdelning_admin)

@bp.route("/veckovy")
@require_roles("superuser","admin")
def veckovy():
    # TODO: implement week summary view reuse unified menu_service
    return redirect(url_for("legacy_kommun_ui.adminpanel"))

@bp.route("/rapport", methods=["GET","POST"])
@require_roles("superuser","admin")
def rapport():
    # TODO: implement reporting mapped to unified attendance/service metrics
    return redirect(url_for("legacy_kommun_ui.adminpanel"))

@bp.route("/redigera_boende")
@require_roles("superuser","admin")
def redigera_boende():
    # TODO: implement editing of per-day attendance (maps to Attendance model)
    return redirect(url_for("legacy_kommun_ui.adminpanel"))
