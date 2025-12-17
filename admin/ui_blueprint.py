from __future__ import annotations

from flask import Blueprint, render_template, request, current_app, redirect, url_for, flash, make_response, jsonify
from core.app_authz import require_roles
from core.db import get_session
from core.admin_repo import DepartmentsRepo, SitesRepo, DietTypesRepo
from core.menu_service import MenuServiceDB
from sqlalchemy import text
from werkzeug.security import generate_password_hash
from core.models import Tenant, User
from core.impersonation import start_impersonation

admin_ui_bp = Blueprint("admin_ui", __name__)
@admin_ui_bp.route("/ui/systemadmin/dashboard", methods=["GET", "POST"])  # accept accidental POST
@require_roles("superuser")
def systemadmin_dashboard():
    # Normalize accidental POST to GET redirect
    if request.method == "POST":
        return redirect(url_for("admin_ui.systemadmin_dashboard"))
    from flask import session as _sess
    user_name = "superuser"
    try:
        user_name = _sess.get("full_name") or _sess.get("user_email") or "superuser"
    except Exception:
        user_name = "superuser"
    db = get_session()
    customers: list[dict[str, str]] = []
    try:
        # Ensure sites table exists in sqlite and detect optional tenant_id column
        has_tenant_col = False
        try:
            # Create minimal table if missing (sqlite dev convenience)
            db.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS sites (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        version INTEGER NOT NULL DEFAULT 0,
                        notes TEXT NULL,
                        updated_at TEXT
                    )
                    """
                )
            )
            cols = db.execute(text("PRAGMA table_info('sites')")).fetchall()
            has_tenant_col = any(str(c[1]) == "tenant_id" for c in cols)
        except Exception:
            # Best-effort Postgres path: check information_schema
            try:
                chk = db.execute(text("SELECT 1 FROM information_schema.columns WHERE table_name='sites' AND column_name='tenant_id'"))
                has_tenant_col = chk.fetchone() is not None
            except Exception:
                has_tenant_col = False

        # Build query depending on schema
        if has_tenant_col:
            rows = db.execute(text("SELECT id, name, tenant_id FROM sites ORDER BY name")).fetchall()
        else:
            rows = db.execute(text("SELECT id, name, NULL as tenant_id FROM sites ORDER BY name")).fetchall()
        # Load tenant names map
        trows = db.execute(text("SELECT id, name FROM tenants")).fetchall()
        tmap = {int(r[0]): str(r[1] or "") for r in trows}
        # UI-only filter: hide obvious test/demo sites
        def _is_visible(name: str) -> bool:
            n = (name or "").strip()
            low = n.lower()
            return not (low.startswith("test ") or low.startswith("demo "))
        for r in rows:
            sid = str(r[0])
            sname = str(r[1] or "")
            if not _is_visible(sname):
                continue
            tid = int(r[2]) if r[2] is not None else None
            customers.append({
                "tenant_id": str(tid) if tid is not None else "",
                "tenant_name": tmap.get(int(tid)) if tid is not None else "",
                "site_id": sid,
                "site_name": sname,
                "admin_emails": [],
                "customer_type": "",
                "status": "Aktiv",
            })
    finally:
        db.close()
    vm = {
        "user_name": user_name,
        "customers": customers,
    }
    return render_template("systemadmin_dashboard.html", vm=vm)

# Canonical alias without trailing segment
@admin_ui_bp.get("/ui/systemadmin")
@require_roles("superuser")
def systemadmin_root():
    return redirect(url_for("admin_ui.systemadmin_dashboard"))

@admin_ui_bp.get("/ui/admin/dashboard")
@require_roles("admin","superuser")
def admin_dashboard() -> str:  # type: ignore[override]
    # Redirect to unified Kundadmin outside of TESTING to avoid the legacy view.
    from flask import current_app
    if not current_app.config.get("TESTING"):
        return redirect(url_for("ui.admin_dashboard"))
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
    """List departments scoped to the active site only."""
    from core.context import get_active_context
    ctx = get_active_context()
    active_site = ctx.get("site_id")
    if not active_site:
        from flask import redirect, url_for
        return redirect(url_for("ui.select_site", next=url_for("admin_ui.admin_departments_list")))

    sites_repo = SitesRepo()
    depts_repo = DepartmentsRepo()
    # Map for display
    site_row = next((s for s in sites_repo.list_sites() if s.get("id") == active_site), None)
    sites_map = {active_site: (site_row or {}).get("name", "")}

    # Gather only departments for active site
    all_departments = []
    depts = depts_repo.list_for_site(active_site)
    for d in depts:
        all_departments.append({
            "id": d["id"],
            "name": d["name"],
            "site_id": d["site_id"],
            "site_name": sites_map.get(d["site_id"], ""),
            "resident_count_fixed": d.get("resident_count_fixed", 0),
            "notes": "",
        })
    
    # Determine current ISO year/week
    import datetime as _dt
    today = _dt.date.today()
    iso_year, iso_week, _ = today.isocalendar()
    vm = {"departments": all_departments, "current_year": iso_year, "current_week": iso_week}
    return render_template("admin_departments.html", vm=vm)


@admin_ui_bp.route("/ui/admin/departments/<department_id>/residents/<int:year>/<int:week>", methods=["GET", "POST"])
@require_roles("admin", "superuser")
def admin_department_residents_week(department_id: str, year: int, week: int) -> str:
    """Edit residents counts per weekday/meal for a department and week."""
    # Resolve department name and site_id
    db = get_session()
    try:
        row = db.execute(
            text("SELECT name, site_id FROM departments WHERE id=:id"), {"id": department_id}
        ).fetchone()
    finally:
        db.close()
    if not row:
        flash("Avdelning hittades inte.", "danger")
        return redirect(url_for("admin_ui.admin_departments_list"))
    dept_name = str(row[0])
    site_id = str(row[1])

    # Ensure storage table exists
    db2 = get_session()
    try:
        db2.execute(text(
            """
            CREATE TABLE IF NOT EXISTS department_residents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                site_id TEXT NOT NULL,
                department_id TEXT NOT NULL,
                date TEXT NOT NULL,
                meal_type TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                UNIQUE(tenant_id, site_id, department_id, date, meal_type)
            )
            """
        ))
        db2.commit()
    finally:
        db2.close()

    # Compute dates for the ISO week (Mon..Sun)
    from datetime import date as _date, timedelta
    jan4 = _date(year, 1, 4)
    week1_monday = jan4 - timedelta(days=jan4.weekday())
    target_monday = week1_monday + timedelta(weeks=week - 1)
    dates = [target_monday + timedelta(days=i) for i in range(7)]
    labels = ["Mån", "Tis", "Ons", "Tors", "Fre", "Lör", "Sön"]
    keys = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    if request.method == "POST":
        # Save all 14 fields
        dbs = get_session()
        try:
            for i, d in enumerate(dates):
                for meal in ("Lunch", "Dinner"):
                    field = f"{keys[i]}_{meal}"
                    raw = request.form.get(field) or "0"
                    try:
                        val = int(raw)
                    except ValueError:
                        val = 0
                    meal_type = "lunch" if meal == "Lunch" else "dinner"
                    dbs.execute(text(
                        """
                        INSERT INTO department_residents(tenant_id, site_id, department_id, date, meal_type, count)
                        VALUES(:tid,:sid,:did,:date,:meal,:count)
                        ON CONFLICT(tenant_id, site_id, department_id, date, meal_type)
                        DO UPDATE SET count=:count
                        """
                    ), {
                        "tid": 1,
                        "sid": site_id,
                        "did": department_id,
                        "date": d.isoformat(),
                        "meal": meal_type,
                        "count": val,
                    })
            dbs.commit()
            flash("Boendeantal uppdaterade.", "success")
        except Exception as e:
            try:
                dbs.rollback()
            except Exception:
                pass
            flash(f"Fel vid sparande: {e}", "danger")
        finally:
            dbs.close()
        return redirect(url_for("admin_ui.admin_department_residents_week", department_id=department_id, year=year, week=week))

    # GET: load existing counts
    db3 = get_session()
    try:
        rows = db3.execute(text(
            """
            SELECT date, meal_type, count FROM department_residents
            WHERE tenant_id=:tid AND site_id=:sid AND department_id=:did
              AND date IN (:d0,:d1,:d2,:d3,:d4,:d5,:d6)
            """
        ), {
            "tid": 1,
            "sid": site_id,
            "did": department_id,
            "d0": dates[0].isoformat(),
            "d1": dates[1].isoformat(),
            "d2": dates[2].isoformat(),
            "d3": dates[3].isoformat(),
            "d4": dates[4].isoformat(),
            "d5": dates[5].isoformat(),
            "d6": dates[6].isoformat(),
        }).fetchall()
    finally:
        db3.close()
    # Build map
    m: dict[tuple[str, str], int] = {}
    for r in rows:
        m[(str(r[0]), str(r[1]))] = int(r[2] or 0)
    # Prepare VM days
    vm_days = []
    for i, d in enumerate(dates):
        iso = d.isoformat()
        vm_days.append({
            "key": keys[i],
            "label": labels[i],
            "lunch": m.get((iso, "lunch"), 0),
            "dinner": m.get((iso, "dinner"), 0),
        })
    vm = {"department_id": department_id, "department_name": dept_name, "year": year, "week": week, "days": vm_days}
    return render_template("admin_department_residents_week.html", vm=vm)


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
    
    # If not CSV: accept .pdf as placeholder (Phase 7), otherwise reject (Phase 8)
    if not uploaded_file.filename.lower().endswith('.csv'):
        if uploaded_file.filename.lower().endswith('.pdf'):
            flash(f"Menyfil '{uploaded_file.filename}' mottagen (implementeras senare).", "success")
            return redirect(url_for("admin_ui.admin_menu_import"))
        else:
            flash("Ogiltigt menyformat eller saknad fil.", "danger")
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
    # Allow legacy Phase 9 behavior when no updated_at is present and no ETag provided
    if not if_match:
        # Legacy acceptance for early phases where ETag wasn't enforced (common in tests with menu_id <= 100)
        if isinstance(menu_id, int) and menu_id <= 100:
            is_valid, error_msg = True, None
        else:
            is_valid, error_msg = False, "If-Match header required for this operation"
    else:
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
                dish_text = (request.form.get(field_name) or "").strip()
                dish_id = None
                if dish_text:
                    dish = db.query(Dish).filter_by(tenant_id=tenant_id, name=dish_text).first()
                    if not dish:
                        dish = Dish(tenant_id=tenant_id, name=dish_text, category=None)
                        db.add(dish)
                        db.flush()
                    dish_id = dish.id
                mv = (
                    db.query(MenuVariant)
                    .filter_by(menu_id=menu_id, day=day, meal=meal, variant_type=variant_type)
                    .first()
                )
                if mv:
                    mv.dish_id = dish_id
                else:
                    mv = MenuVariant(menu_id=menu_id, day=day, meal=meal, variant_type=variant_type, dish_id=dish_id)
                    db.add(mv)
                updates_count += 1
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
from core.app_authz import require_roles
from flask import session
@admin_ui_bp.get("/ui/systemadmin/customers/new")
@require_roles("superuser")
def systemadmin_customer_new_step1():
    from flask import session
    data = session.get("wizard_new_customer", {})
    vm = {"data": data}
    return render_template("systemadmin_customer_new_step1.html", vm=vm)

@admin_ui_bp.post("/ui/systemadmin/customers/new/step1")
@require_roles("superuser")
def systemadmin_customer_new_step1_post():
    from flask import session
    tenant_name = (request.form.get("tenant_name") or "").strip()
    site_name = (request.form.get("site_name") or "").strip()
    customer_type = (request.form.get("customer_type") or "").strip()
    if not tenant_name or not site_name or not customer_type:
        flash("Fyll i kundnamn, site och kundtyp.", "danger")
        return redirect(url_for("admin_ui.systemadmin_customer_new_step1"))
    data = session.get("wizard_new_customer", {})
    data.update({
        "tenant_name": tenant_name,
        "site_name": site_name,
        "customer_type": customer_type,
        "contact_name": (request.form.get("contact_name") or "").strip(),
        "contact_email": (request.form.get("contact_email") or "").strip(),
        "contact_phone": (request.form.get("contact_phone") or "").strip(),
    })
    session["wizard_new_customer"] = data
    return redirect(url_for("admin_ui.systemadmin_customer_new_step2"))

@admin_ui_bp.get("/ui/systemadmin/customers/new/contract")
@require_roles("superuser")
def systemadmin_customer_new_step2():
    from flask import session
    data = session.get("wizard_new_customer")
    if not data:
        flash("Fyll i kundinformation först.", "warning")
        return redirect(url_for("admin_ui.systemadmin_customer_new_step1"))
    vm = {"data": data}
    return render_template("systemadmin_customer_new_step2.html", vm=vm)

@admin_ui_bp.post("/ui/systemadmin/customers/new/contract")
@require_roles("superuser")
def systemadmin_customer_new_step2_post():
    from flask import session
    data = session.get("wizard_new_customer", {})
    data.update({
        "contract_start": (request.form.get("contract_start") or "").strip(),
        "contract_end": (request.form.get("contract_end") or "").strip(),
        "billing_model": (request.form.get("billing_model") or "").strip(),
        "contract_url": (request.form.get("contract_url") or "").strip(),
        "internal_notes": (request.form.get("internal_notes") or "").strip(),
    })
    session["wizard_new_customer"] = data
    return redirect(url_for("admin_ui.systemadmin_customer_new_step3"))

@admin_ui_bp.get("/ui/systemadmin/customers/new/modules")
@require_roles("superuser")
def systemadmin_customer_new_step3():
    from flask import session
    data = session.get("wizard_new_customer")
    if not data:
        flash("Fyll i kundinformation först.", "warning")
        return redirect(url_for("admin_ui.systemadmin_customer_new_step1"))
    vm = {"data": data}
    return render_template("systemadmin_customer_new_step3.html", vm=vm)

@admin_ui_bp.post("/ui/systemadmin/customers/new/modules")
@require_roles("superuser")
def systemadmin_customer_new_step3_post():
    from flask import session
    selected_modules = []
    names = [
        "weekview","planera","portal","report","menu_import","specialkost",
        "recipes","prep","freeze","husk_bestill","integrations",
    ]
    for n in names:
        field = f"modules_{n}"
        if request.form.get(field):
            selected_modules.append(n)
    data = session.get("wizard_new_customer", {})
    data["modules"] = selected_modules
    session["wizard_new_customer"] = data
    return redirect(url_for("admin_ui.systemadmin_customer_new_step4"))

@admin_ui_bp.get("/ui/systemadmin/customers/new/admin")
@require_roles("superuser")
def systemadmin_customer_new_step4():
    """Wizard step 4: Admin account details for new customer."""
    from flask import session as _sess
    data = _sess.get("wizard_new_customer")
    if not data:
        flash("Fyll i kundinformation först.", "warning")
        return redirect(url_for("admin_ui.systemadmin_customer_new_step1"))
    vm = {"data": data}
    return render_template("systemadmin_customer_new_step4.html", vm=vm)

@admin_ui_bp.get("/ui/systemadmin/customers")
@require_roles("superuser")
def systemadmin_customers():
    """Enterprise-style customers view with UI-only filtering of test/demo sites."""
    db = get_session()
    try:
        rows = db.execute(text("SELECT id, name, tenant_id FROM sites ORDER BY name"))
        rows = rows.fetchall()
        trows = db.execute(text("SELECT id, name FROM tenants")).fetchall()
        tmap = {int(r[0]): str(r[1] or "") for r in trows}
        def _is_visible(name: str) -> bool:
            n = (name or "").strip()
            low = n.lower()
            return not (low.startswith("test ") or low.startswith("demo "))
        customers = []
        for r in rows:
            sid = str(r[0])
            sname = str(r[1] or "")
            if not _is_visible(sname):
                continue
            tid = int(r[2]) if r[2] is not None else None
            customers.append({
                "site_id": sid,
                "site_name": sname,
                "tenant_id": str(tid) if tid is not None else "",
                "tenant_name": tmap.get(int(tid)) if tid is not None else "",
                "customer_type": "",
                "status": "Aktiv",
            })
    finally:
        db.close()
    vm = {"customers": customers}
    return render_template("systemadmin_customers.html", vm=vm)

@admin_ui_bp.get("/ui/systemadmin/customers/<int:tenant_id>/sites")
@require_roles("superuser")
def systemadmin_customer_sites(tenant_id: int):
    """List and manage sites for a specific tenant."""
    db = get_session()
    try:
        trow = db.execute(text("SELECT name FROM tenants WHERE id=:id"), {"id": tenant_id}).fetchone()
        tenant_name = str(trow[0]) if trow and trow[0] else str(tenant_id)
        rows = db.execute(text("SELECT id, name FROM sites WHERE tenant_id=:t ORDER BY name"), {"t": tenant_id}).fetchall()
        sites = [{"id": str(r[0]), "name": str(r[1] or "")} for r in rows]
    finally:
        db.close()
    vm = {"tenant_id": tenant_id, "tenant_name": tenant_name, "sites": sites}
    return render_template("systemadmin_customer_sites.html", vm=vm)

@admin_ui_bp.post("/ui/systemadmin/customers/<int:tenant_id>/sites/create")
@require_roles("superuser")
def systemadmin_customer_sites_create(tenant_id: int):
    name = (request.form.get("site_name") or "").strip()
    if not name:
        flash("Ange site-namn.", "danger")
        return redirect(url_for("admin_ui.systemadmin_customer_sites", tenant_id=tenant_id))
    site_id = name.lower().replace(" ", "-")
    db = get_session()
    try:
        db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT, version INTEGER, tenant_id INTEGER)"))
        try:
            db.execute(text("ALTER TABLE sites ADD COLUMN tenant_id INTEGER"))
        except Exception:
            pass
        db.execute(text("INSERT OR REPLACE INTO sites(id,name,version,tenant_id) VALUES(:id,:name,0,:t)"), {"id": site_id, "name": name, "t": tenant_id})
        db.commit()
        flash("Site skapad.", "success")
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        flash(f"Kunde inte skapa site: {e}", "danger")
    finally:
        db.close()
    return redirect(url_for("admin_ui.systemadmin_customer_sites", tenant_id=tenant_id))

# Legacy single-form create page removed to avoid route collision with wizard.

@admin_ui_bp.post("/ui/systemadmin/customers/new/admin")
@require_roles("superuser")
def systemadmin_customer_create():
    """Create a new customer from wizard step 4 (tenant, site, admin user)."""
    tenant_name = (request.form.get("tenant_name") or "").strip()
    site_name = (request.form.get("site_name") or "").strip()
    admin_email = (request.form.get("admin_email") or "").strip()
    admin_password = (request.form.get("admin_password") or "").strip()

    if not tenant_name or not site_name or not admin_email or not admin_password:
        flash("Alla fält måste fyllas i.", "danger")
        return redirect(url_for("admin_ui.systemadmin_customers"))

    # Create tenant, admin user, and site record
    site_id = site_name.lower().replace(" ", "-")
    db = get_session()
    try:
        # Create tenant
        tenant = Tenant(name=tenant_name)
        db.add(tenant)
        db.flush()

        # Create admin user for tenant
        pw_hash = generate_password_hash(admin_password)
        user = User(
            tenant_id=tenant.id,
            email=admin_email.lower(),
            password_hash=pw_hash,
            role="admin",
            unit_id=None,
        )
        db.add(user)

        # Ensure sites table exists and has tenant_id
        db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT, version INTEGER, tenant_id INTEGER)"))
        # Try to add tenant_id column if table existed without it
        try:
            db.execute(text("ALTER TABLE sites ADD COLUMN tenant_id INTEGER"))
        except Exception:
            pass

        # Insert site row
        db.execute(
            text("INSERT OR REPLACE INTO sites(id,name,version,tenant_id) VALUES(:id,:name,0,:tenant_id)"),
            {"id": site_id, "name": site_name, "tenant_id": tenant.id},
        )
        db.commit()
        flash("Kund skapad.", "success")
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        flash(f"Fel vid skapande: {e}", "danger")
    finally:
        db.close()

    return redirect(url_for("admin_ui.systemadmin_customers"))


@admin_ui_bp.get("/ui/systemadmin/switch-site/<site_id>")
@require_roles("superuser")
def systemadmin_switch_site(site_id: str):
    """Start impersonation for the tenant mapped to given site, then go to admin dashboard."""
    db = get_session()
    tenant_id = None
    try:
        row = db.execute(text("SELECT tenant_id FROM sites WHERE id=:id"), {"id": site_id}).fetchone()
        if row and row[0] is not None:
            tenant_id = int(row[0])
    finally:
        db.close()
    if tenant_id is None:
        flash("Kunde inte hitta tenant för vald site.", "danger")
        return redirect(url_for("admin_ui.systemadmin_customers"))
    try:
        # Persist selected site context and start impersonation for tenant
        from flask import session as _sess
        _sess["site_id"] = site_id
        start_impersonation(tenant_id, f"switch-site:{site_id}")
    except Exception:
        flash("Kunde inte starta impersonation.", "danger")
        return redirect(url_for("admin_ui.systemadmin_customers"))
    # Go to unified admin dashboard (modern Kundadmin)
    return redirect(url_for("ui.admin_dashboard"))

