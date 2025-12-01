from __future__ import annotations

from flask import Blueprint, render_template, request, current_app, redirect, url_for, flash, make_response, jsonify
from core.app_authz import require_roles
from core.db import get_session
from core.admin_repo import DepartmentsRepo, SitesRepo, DietTypesRepo
from core.menu_service import MenuServiceDB
from sqlalchemy import text

admin_ui_bp = Blueprint("admin_ui", __name__)

@admin_ui_bp.get("/ui/admin/dashboard")
@require_roles("admin","superuser")
def admin_dashboard() -> str:  # type: ignore[override]
    # Feature flag gate (future extension). Currently always enabled in tests via ff.admin.enabled.
    db = get_session()
    try:
        sites_rows = db.execute(text("SELECT id, name FROM sites ORDER BY name")).fetchall()
        sites = [(str(r[0]), str(r[1])) for r in sites_rows]
        selected_site_id = (request.args.get("site_id") or "").strip() or None
        if not selected_site_id and sites:
            selected_site_id = sites[0][0]
        departments: list[tuple[str, str]] = []
        if selected_site_id:
            dep_rows = db.execute(
                text("SELECT id, name FROM departments WHERE site_id=:s ORDER BY name"),
                {"s": selected_site_id},
            ).fetchall()
            departments = [(str(r[0]), str(r[1])) for r in dep_rows]
    finally:
        db.close()
    # Module definitions with feature flag gating. Flag naming convention: ff.<key>.enabled
    # TODO: Replace fallback True with customer-specific provisioning (Phase X)
    registry = getattr(current_app, "feature_registry", None)
    def _is_enabled(key: str) -> bool:
        flag = f"ff.{key}.enabled"
        try:
            if registry and registry.has(flag):
                return bool(registry.enabled(flag))
        except Exception:  # pragma: no cover - defensive
            pass
        return True  # fallback for backward compatibility

    modules_def = [
        {"key": "departments", "title": "Avdelningar", "description": "Hantera avdelningar", "url": "/ui/admin/departments", "icon": "📋"},
        {"key": "portal", "title": "Avdelningsportal", "description": "Dagliga val & menyer", "url": "/ui/portal/department/week", "icon": "🍽️"},
        {"key": "planera", "title": "Planera", "description": "Planering per dag", "url": "/ui/planera/day", "icon": "🧾"},
        {"key": "report", "title": "Rapport", "description": "Översikter & summeringar", "url": "/ui/reports/weekview", "icon": "📊"},
        {"key": "menuimport", "title": "Menyimport", "description": "Importera menyer", "url": "/ui/admin/menu-import", "icon": "📥"},
        {"key": "specialdiets", "title": "Specialkost", "description": "Hantera kosttyper", "url": "/ui/admin/specialkost", "icon": "🥦"},
        {"key": "recipes", "title": "Recept", "description": "Recept & måltider", "url": "#", "icon": "🍳"},
        {"key": "turnus", "title": "Turnus", "description": "Schemaläggning", "url": "#", "icon": "🔁"},
        {"key": "huska", "title": "Husk å bestill", "description": "Beställningslista", "url": "#", "icon": "📦"},
    ]
    # Apply enable logic first, then filter out disabled so template simpler
    modules = []
    for m in modules_def:
        enabled = _is_enabled(m["key"]) if m["key"] != "departments" else True  # departments always visible
        if enabled:
            modules.append({**m, "enabled": True})
    vm = {"sites": sites, "selected_site_id": selected_site_id, "departments": departments, "modules": modules}
    return render_template("admin_dashboard.html", vm=vm)


@admin_ui_bp.get("/ui/admin/departments")
@require_roles("admin", "superuser")
def admin_departments_list() -> str:  # type: ignore[override]
    """List all departments across all sites with site names."""
    sites_repo = SitesRepo()
    depts_repo = DepartmentsRepo()
    sites_data = sites_repo.list_sites()
    sites_map = {s["id"]: s["name"] for s in sites_data}
    
    # Gather all departments across all sites
    all_departments = []
    for site in sites_data:
        depts = depts_repo.list_for_site(site["id"])
        for d in depts:
            all_departments.append({
                "id": d["id"],
                "name": d["name"],
                "site_id": d["site_id"],
                "site_name": sites_map.get(d["site_id"], ""),
                "resident_count_fixed": d.get("resident_count_fixed", 0),
                "notes": "",  # TODO: fetch notes from department_notes table if needed
            })
    
    vm = {"departments": all_departments}
    return render_template("admin_departments.html", vm=vm)


@admin_ui_bp.route("/ui/admin/departments/<department_id>/edit", methods=["GET", "POST"])
@require_roles("admin", "superuser")
def admin_department_edit(department_id: str) -> str:  # type: ignore[override]
    """Edit a single department (name, resident_count_fixed, notes). TODO: Add ETag concurrency control."""
    depts_repo = DepartmentsRepo()
    
    if request.method == "POST":
        new_name = (request.form.get("name") or "").strip()
        new_count = request.form.get("resident_count_fixed") or "0"
        new_notes = (request.form.get("notes") or "").strip()
        
        try:
            count_int = int(new_count)
        except ValueError:
            count_int = 0
        
        # TODO: Implement ETag-based optimistic concurrency (fetch version, pass to update_department)
        # For now, fetch current version and do a simple update
        current_version = depts_repo.get_version(department_id)
        if current_version is None:
            flash("Avdelning hittades inte.", "danger")
            return redirect(url_for("admin_ui.admin_departments_list"))
        
        try:
            depts_repo.update_department(
                department_id,
                current_version,
                name=new_name,
                resident_count_fixed=count_int,
                notes=new_notes,
            )
            flash(f"Avdelning '{new_name}' uppdaterad.", "success")
        except Exception as e:
            flash(f"Fel vid uppdatering: {e}", "danger")
        
        return redirect(url_for("admin_ui.admin_departments_list"))
    
    # GET: fetch department data
    db = get_session()
    try:
        row = db.execute(
            text("SELECT id, site_id, name, resident_count_fixed, notes FROM departments WHERE id=:id"),
            {"id": department_id},
        ).fetchone()
    finally:
        db.close()
    
    if not row:
        flash("Avdelning hittades inte.", "danger")
        return redirect(url_for("admin_ui.admin_departments_list"))
    
    dept = {
        "id": str(row[0]),
        "site_id": str(row[1]),
        "name": str(row[2]) if row[2] else "",
        "resident_count_fixed": int(row[3] or 0),
        "notes": str(row[4]) if row[4] else "",
    }
    
    vm = {"department": dept}
    return render_template("admin_department_edit.html", vm=vm)


@admin_ui_bp.get("/ui/admin/specialkost")
@require_roles("admin", "superuser")
def admin_specialkost_list() -> str:  # type: ignore[override]
    """List all dietary types (specialkost)."""
    repo = DietTypesRepo()
    diet_types = repo.list_all(tenant_id=1)
    vm = {"diet_types": diet_types}
    return render_template("admin_specialkost.html", vm=vm)


@admin_ui_bp.route("/ui/admin/specialkost/new", methods=["GET", "POST"])
@require_roles("admin", "superuser")
def admin_specialkost_new() -> str:  # type: ignore[override]
    """Create a new dietary type."""
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        default_select = request.form.get("default_select") == "on"
        
        if not name:
            flash("Namn måste anges.", "danger")
            return render_template("admin_specialkost_new.html", vm={})
        
        repo = DietTypesRepo()
        try:
            repo.create(tenant_id=1, name=name, default_select=default_select)
            flash(f"Kosttyp '{name}' skapad.", "success")
        except Exception as e:
            flash(f"Fel vid skapande: {e}", "danger")
        
        return redirect(url_for("admin_ui.admin_specialkost_list"))
    
    vm = {}
    return render_template("admin_specialkost_new.html", vm=vm)


@admin_ui_bp.route("/ui/admin/specialkost/<int:kosttyp_id>/edit", methods=["GET", "POST"])
@require_roles("admin", "superuser")
def admin_specialkost_edit(kosttyp_id: int) -> str:  # type: ignore[override]
    """Edit a dietary type. TODO: Add ETag concurrency control."""
    repo = DietTypesRepo()
    
    if request.method == "POST":
        new_name = (request.form.get("name") or "").strip()
        new_default_select = request.form.get("default_select") == "on"
        
        if not new_name:
            flash("Namn måste anges.", "danger")
            return redirect(url_for("admin_ui.admin_specialkost_edit", kosttyp_id=kosttyp_id))
        
        try:
            repo.update(kosttyp_id, name=new_name, default_select=new_default_select)
            flash(f"Kosttyp '{new_name}' uppdaterad.", "success")
        except Exception as e:
            flash(f"Fel vid uppdatering: {e}", "danger")
        
        return redirect(url_for("admin_ui.admin_specialkost_list"))
    
    # GET: fetch dietary type
    diet_type = repo.get_by_id(kosttyp_id)
    if not diet_type:
        flash("Kosttyp hittades inte.", "danger")
        return redirect(url_for("admin_ui.admin_specialkost_list"))
    
    vm = {"diet_type": diet_type}
    return render_template("admin_specialkost_edit.html", vm=vm)


@admin_ui_bp.post("/ui/admin/specialkost/<int:kosttyp_id>/delete")
@require_roles("admin", "superuser")
def admin_specialkost_delete(kosttyp_id: int) -> str:  # type: ignore[override]
    """Delete a dietary type."""
    repo = DietTypesRepo()
    try:
        diet_type = repo.get_by_id(kosttyp_id)
        name = diet_type["name"] if diet_type else "okänd"
        repo.delete(kosttyp_id)
        flash(f"Kosttyp '{name}' borttagen.", "success")
    except Exception as e:
        flash(f"Fel vid borttagning: {e}", "danger")
    
    return redirect(url_for("admin_ui.admin_specialkost_list"))


# ========================================
# Admin Phase 7: Menu Import (MVP)
# ========================================

@admin_ui_bp.get("/ui/admin/menu-import")
@require_roles("admin", "superuser")
def admin_menu_import() -> str:  # type: ignore[override]
    """Display menu import page with file upload form and list of weeks with menu data."""
    tenant_id = 1  # TODO: Extract from session when multi-tenancy enabled
    
    # Fetch all unique (year, week) combinations from menus table
    db = get_session()
    try:
        rows = db.execute(
            text("""
                SELECT DISTINCT year, week 
                FROM menus 
                WHERE tenant_id = :tid 
                ORDER BY year DESC, week DESC
            """),
            {"tid": tenant_id}
        ).fetchall()
        weeks = [{"year": r[0], "week": r[1]} for r in rows]
    finally:
        db.close()
    
    vm = {"weeks": weeks}
    return render_template("admin_menu_import.html", vm=vm)


@admin_ui_bp.post("/ui/admin/menu-import/upload")
@require_roles("admin", "superuser")
def admin_menu_import_upload() -> str:  # type: ignore[override]
    """Handle CSV menu file upload and import."""
    from core.menu_csv_parser import parse_menu_csv, csv_rows_to_import_result, MenuCSVParseError
    from core.menu_import_service import MenuImportService
    from core.menu_service import MenuServiceDB
    
    tenant_id = 1  # TODO: Extract from session when multi-tenancy enabled
    uploaded_file = request.files.get("menu_file")
    
    if not uploaded_file or uploaded_file.filename == "":
        flash("Ingen fil vald.", "danger")
        return redirect(url_for("admin_ui.admin_menu_import"))
    
    # Validate CSV file extension
    if not uploaded_file.filename.lower().endswith('.csv'):
        flash("Ogiltigt menyformat. Endast CSV-filer stöds.", "danger")
        return redirect(url_for("admin_ui.admin_menu_import"))
    
    try:
        # Parse CSV
        rows = parse_menu_csv(uploaded_file.stream)
        import_result = csv_rows_to_import_result(rows)
        
        # Apply import using MenuImportService
        menu_service = MenuServiceDB()
        import_service = MenuImportService(menu_service)
        summary = import_service.apply(tenant_id, import_result)
        
        # Show success message with summary
        weeks_imported = len(import_result.weeks)
        flash(
            f"Menyn importerad: {summary['created']} skapade, "
            f"{summary['updated']} uppdaterade, "
            f"{summary['skipped']} hoppade över ({weeks_imported} veckor).",
            "success"
        )
        return redirect(url_for("admin_ui.admin_menu_import"))
        
    except MenuCSVParseError as e:
        flash(f"Ogiltigt menyformat: {e}", "danger")
        return redirect(url_for("admin_ui.admin_menu_import"))
    except Exception as e:
        flash(f"Importfel: {e}", "danger")
        return redirect(url_for("admin_ui.admin_menu_import"))


@admin_ui_bp.get("/ui/admin/menu-import/week/<int:year>/<int:week>")
@require_roles("admin", "superuser")
def admin_menu_import_week(year: int, week: int) -> str:  # type: ignore[override]
    """Display menu variants for a specific week."""
    from core.etag_utils import generate_menu_etag
    
    tenant_id = 1  # TODO: Extract from session
    
    menu_service = MenuServiceDB()
    week_view = menu_service.get_week_view(tenant_id, week, year)
    
    if not week_view or not week_view.get("menu_id"):
        flash(f"Ingen meny hittades för vecka {week}/{year}.", "warning")
        return redirect(url_for("admin_ui.admin_menu_import"))
    
    # Generate ETag for optimistic locking
    etag = generate_menu_etag(week_view["menu_id"], week_view["updated_at"])
    
    vm = {
        "year": year,
        "week": week,
        "menu_id": week_view["menu_id"],
        "menu_status": week_view.get("menu_status", "draft"),
        "etag": etag,
        "days": week_view.get("days", {})
    }
    
    response = make_response(render_template("admin_menu_import_week.html", vm=vm))
    response.headers["ETag"] = etag
    return response


@admin_ui_bp.get("/ui/admin/menu-import/week/<int:year>/<int:week>/edit")
@require_roles("admin", "superuser")
def admin_menu_import_week_edit(year: int, week: int) -> str:  # type: ignore[override]
    """Edit menu variants for a specific week."""
    from core.etag_utils import generate_menu_etag
    
    tenant_id = 1  # TODO: Extract from session
    
    menu_service = MenuServiceDB()
    week_view = menu_service.get_week_view(tenant_id, week, year)
    
    if not week_view or not week_view.get("menu_id"):
        flash(f"Ingen meny hittades för vecka {week}/{year}.", "warning")
        return redirect(url_for("admin_ui.admin_menu_import"))
    
    # Generate ETag
    etag = generate_menu_etag(week_view["menu_id"], week_view["updated_at"])
    
    vm = {
        "year": year,
        "week": week,
        "menu_id": week_view["menu_id"],
        "etag": etag,
        "days": week_view.get("days", {})
    }
    return render_template("admin_menu_import_week_edit.html", vm=vm)


@admin_ui_bp.post("/ui/admin/menu-import/week/<int:year>/<int:week>/save")
@require_roles("admin", "superuser")
def admin_menu_import_week_save(year: int, week: int) -> str:  # type: ignore[override]
    """Save edited menu variants for a specific week."""
    from core.db import get_session
    from core.models import Dish, Menu
    from core.etag_utils import validate_etag
    
    tenant_id = 1  # TODO: Extract from session
    
    menu_service = MenuServiceDB()
    week_view = menu_service.get_week_view(tenant_id, week, year)
    
    if not week_view or not week_view.get("menu_id"):
        flash(f"Ingen meny hittades för vecka {week}/{year}.", "danger")
        return redirect(url_for("admin_ui.admin_menu_import"))
    
    menu_id = week_view["menu_id"]
    
    # Validate ETag from If-Match header or form data
    if_match = request.headers.get("If-Match") or request.form.get("_etag")
    is_valid, error_msg = validate_etag(if_match, menu_id, week_view["updated_at"])
    
    if not is_valid:
        # Return 412 Precondition Failed for AJAX, flash for form submit
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({
                "type": "https://unified.example/errors/precondition-failed",
                "title": "Precondition Failed",
                "status": 412,
                "detail": error_msg
            }), 412
        else:
            flash(f"Konflikt: {error_msg} Ladda om sidan för att se senaste versionen.", "warning")
            return redirect(url_for("admin_ui.admin_menu_import_week_edit", year=year, week=week))
    
    # Days in Swedish
    days = ["Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag", "Lördag", "Söndag"]
    meals_variants = [
        ("Lunch", "alt1"),
        ("Lunch", "alt2"),
        ("Lunch", "dessert"),
        ("Kväll", "kvall")
    ]
    
    # Process form data
    updates_count = 0
    db = get_session()
    try:
        for day in days:
            for meal, variant_type in meals_variants:
                field_name = f"{day}_{meal}_{variant_type}"
                dish_text = request.form.get(field_name, "").strip()
                
                # Get or create dish by name
                dish_id = None
                if dish_text:
                    # Look for existing dish with exact name
                    dish = db.query(Dish).filter_by(tenant_id=tenant_id, name=dish_text).first()
                    if not dish:
                        # Create new dish
                        dish = Dish(tenant_id=tenant_id, name=dish_text, category=None)
                        db.add(dish)
                        db.flush()  # Get the ID
                    dish_id = dish.id
                
                # Update variant (empty allowed - dish_id will be None)
                try:
                    menu_service.set_variant(
                        tenant_id=tenant_id,
                        menu_id=menu_id,
                        day=day,
                        meal=meal,
                        variant_type=variant_type,
                        dish_id=dish_id
                    )
                    updates_count += 1
                except Exception as e:
                    flash(f"Fel vid uppdatering av {day} {meal} {variant_type}: {e}", "danger")
        
        # Update menu's updated_at timestamp
        menu = db.query(Menu).filter_by(id=menu_id).first()
        if menu:
            from datetime import datetime, timezone
            menu.updated_at = datetime.now(timezone.utc)
        
        db.commit()
    finally:
        db.close()
    
    flash(f"Menyn uppdaterad ({updates_count} ändringar sparade).", "success")
    return redirect(url_for("admin_ui.admin_menu_import_week", year=year, week=week))


@admin_ui_bp.post("/ui/admin/menu-import/week/<int:year>/<int:week>/publish")
@require_roles("admin", "superuser")
def admin_menu_import_week_publish(year: int, week: int) -> str:  # type: ignore[override]
    """Publish a menu week (set status to 'published')."""
    from core.etag_utils import validate_etag
    
    tenant_id = 1  # TODO: Extract from session
    
    menu_service = MenuServiceDB()
    week_view = menu_service.get_week_view(tenant_id, week, year)
    
    if not week_view or not week_view.get("menu_id"):
        flash(f"Ingen meny hittades för vecka {week}/{year}.", "danger")
        return redirect(url_for("admin_ui.admin_menu_import"))
    
    menu_id = week_view["menu_id"]
    
    # Validate ETag from If-Match header or form data
    if_match = request.headers.get("If-Match") or request.form.get("_etag")
    is_valid, error_msg = validate_etag(if_match, menu_id, week_view["updated_at"])
    
    if not is_valid:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({
                "type": "https://unified.example/errors/precondition-failed",
                "title": "Precondition Failed",
                "status": 412,
                "detail": error_msg
            }), 412
        else:
            flash(f"Konflikt: {error_msg} Ladda om sidan för att se senaste versionen.", "warning")
            return redirect(url_for("admin_ui.admin_menu_import_week", year=year, week=week))
    
    try:
        menu_service.publish_menu(tenant_id, menu_id)
        flash(f"Vecka {week} publicerad.", "success")
    except Exception as e:
        flash(f"Fel vid publicering: {e}", "danger")
    
    return redirect(url_for("admin_ui.admin_menu_import_week", year=year, week=week))


@admin_ui_bp.post("/ui/admin/menu-import/week/<int:year>/<int:week>/unpublish")
@require_roles("admin", "superuser")
def admin_menu_import_week_unpublish(year: int, week: int) -> str:  # type: ignore[override]
    """Unpublish a menu week (set status to 'draft')."""
    from core.etag_utils import validate_etag
    
    tenant_id = 1  # TODO: Extract from session
    
    menu_service = MenuServiceDB()
    week_view = menu_service.get_week_view(tenant_id, week, year)
    
    if not week_view or not week_view.get("menu_id"):
        flash(f"Ingen meny hittades för vecka {week}/{year}.", "danger")
        return redirect(url_for("admin_ui.admin_menu_import"))
    
    menu_id = week_view["menu_id"]
    
    # Validate ETag from If-Match header or form data
    if_match = request.headers.get("If-Match") or request.form.get("_etag")
    is_valid, error_msg = validate_etag(if_match, menu_id, week_view["updated_at"])
    
    if not is_valid:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({
                "type": "https://unified.example/errors/precondition-failed",
                "title": "Precondition Failed",
                "status": 412,
                "detail": error_msg
            }), 412
        else:
            flash(f"Konflikt: {error_msg} Ladda om sidan för att se senaste versionen.", "warning")
            return redirect(url_for("admin_ui.admin_menu_import_week", year=year, week=week))
    
    try:
        menu_service.unpublish_menu(tenant_id, menu_id)
        flash(f"Vecka {week} satt till utkast.", "success")
    except Exception as e:
        flash(f"Fel vid återgång till utkast: {e}", "danger")
    
    return redirect(url_for("admin_ui.admin_menu_import_week", year=year, week=week))


__all__ = ["admin_ui_bp"]
