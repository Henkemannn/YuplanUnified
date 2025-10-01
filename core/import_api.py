from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, session

from .auth import require_roles
from .db import get_session
from .importers.composite import CompositeMenuImporter
from .importers.docx_importer import DocxMenuImporter
from .importers.excel_importer import ExcelMenuImporter
from .menu_import_service import MenuImportService
from .models import Dish, Menu, MenuVariant

bp = Blueprint("import_api", __name__, url_prefix="/import")

# Instantiate a composite importer lazily (could be app-level singleton)
_importer = CompositeMenuImporter([DocxMenuImporter(), ExcelMenuImporter()])

@bp.post("/menu")
@require_roles("superuser","admin","cook")
def import_menu():
    if "file" not in request.files:
        return jsonify({"error": "file missing"}), 400
    file = request.files["file"]
    tenant_id = session.get("tenant_id")
    if not tenant_id:
        return jsonify({"error": "no tenant in session"}), 400
    data = file.read()
    filename = file.filename or "uploaded"
    result = _importer.parse(data, filename, file.mimetype)
    # Apply even if errors? We stop if critical errors.
    if result.errors and not result.weeks:
        return jsonify({"errors": result.errors}), 400
    svc = getattr(current_app, "menu_import_service", None)
    if svc is None:
        # build on the fly
        from .menu_service import MenuServiceDB
        svc = MenuImportService(MenuServiceDB())
        current_app.menu_import_service = svc  # type: ignore
    dry_run = request.args.get("dry_run") in ("1","true","yes")
    if dry_run:
        # Compute prospective changes without writing
        diff = []
        db = get_session()
        try:
            for week_block in result.weeks:
                menu = db.query(Menu).filter_by(tenant_id=tenant_id, week=week_block.week, year=week_block.year).first()
                existing_variants = {}
                if menu:
                    rows = db.query(MenuVariant).filter_by(menu_id=menu.id).all()
                    existing_variants = {(r.day,r.meal,r.variant_type): r.dish_id for r in rows}
                for item in week_block.items:
                    # dish existence
                    dish = db.query(Dish).filter_by(tenant_id=tenant_id, name=item.dish_name).first()
                    prospective_dish_new = dish is None
                    existing_dish_id = dish.id if dish else None
                    key = (item.day,item.meal,item.variant_type)
                    current_variant_dish = existing_variants.get(key)
                    action = "create"
                    if current_variant_dish is not None:
                        if current_variant_dish == existing_dish_id and not prospective_dish_new:
                            action = "skip"
                        else:
                            action = "update"
                    diff.append({
                        "week": week_block.week,
                        "year": week_block.year,
                        "day": item.day,
                        "meal": item.meal,
                        "variant_type": item.variant_type,
                        "dish_name": item.dish_name,
                        "dish_new": prospective_dish_new,
                        "variant_action": action
                    })
        finally:
            db.close()
        return jsonify({"dry_run": True, "diff": diff, "warnings": result.warnings, "errors": result.errors})
    summary = svc.apply(tenant_id, result)
    return jsonify(summary)
