"""
Phase 6: Weekview Redesign (UI) — Tablet-first, premium unified layout
Covers layout elements, navigation, accessibility, and basic regressions.
"""
from datetime import date
import uuid

from sqlalchemy import text


def _h(role: str = "admin"):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def _seed_site_and_department(app, site_id: str, dept_id: str, site_name: str = "Test Site", dept_name: str = "Dept A"):
    from core.db import get_session
    with app.app_context():
        db = get_session()
        try:
            db.execute(
                text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"),
                {"i": site_id, "n": site_name},
            )
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version)\n"
                    "VALUES(:i,:s,:n,'fixed',20,0) ON CONFLICT(id) DO NOTHING"
                ),
                {"i": dept_id, "s": site_id, "n": dept_name},
            )
            db.commit()
        finally:
            db.close()


def _current_year_week():
    t = date.today().isocalendar()
    return t[0], t[1]


def test_weekview_page_structure_and_assets(client_admin):
    app = client_admin.application
    site_id, dept_id = "site_p6_assets", "dept_p6_assets"
    _seed_site_and_department(app, site_id, dept_id)
    year, week = _current_year_week()

    r = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dept_id}&year={year}&week={week}",
        headers=_h("admin"),
    )
    assert r.status_code == 200
    html = r.get_data(as_text=True)

    # Title (browser tab) comes from base block
    assert "<title>Yuplan Unified</title>" in html
    # Visible page H1 title
    assert ">Veckovy</h1>" in html

    # Unified assets linked
    assert '/static/css/unified_weekview.css' in html
    assert '/static/js/unified_weekview.js' in html

    # Shell elements
    assert 'class="yp-card department-card"' in html
    assert 'class="week-grid"' in html


def test_weekview_has_7_day_cells(client_admin):
    app = client_admin.application
    site_id, dept_id = "site_p6_days", "dept_p6_days"
    _seed_site_and_department(app, site_id, dept_id)
    year, week = _current_year_week()

    r = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dept_id}&year={year}&week={week}",
        headers=_h("admin"),
    )
    assert r.status_code == 200
    html = r.get_data(as_text=True)

    # Count day cells in markup (service enriches to 7 days)
    count = html.count('class="day-cell"')
    assert count == 7


def test_weekview_navigation_buttons_and_shortcuts_present(client_admin):
    app = client_admin.application
    site_id, dept_id = "site_p6_nav", "dept_p6_nav"
    _seed_site_and_department(app, site_id, dept_id)
    year, week = _current_year_week()

    r = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dept_id}&year={year}&week={week}",
        headers=_h("admin"),
    )
    assert r.status_code == 200
    html = r.get_data(as_text=True)

    # Touch-friendly buttons in nav
    assert 'data-nav="prev-week"' in html
    assert 'class="weekview-nav-btn weekview-nav-btn--primary"' in html
    assert 'data-nav="next-week"' in html

    # CSS enforces min height for touch targets
    css = client_admin.get('/static/css/unified_weekview.css')
    css_text = css.get_data(as_text=True)
    assert 'min-height: 44px' in css_text


def test_weekview_meal_cells_accessible_with_badges(client_admin):
    app = client_admin.application
    site_id, dept_id = "site_p6_a11y", "dept_p6_a11y"
    _seed_site_and_department(app, site_id, dept_id)
    year, week = _current_year_week()

    r = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dept_id}&year={year}&week={week}",
        headers=_h("admin"),
    )
    assert r.status_code == 200
    html = r.get_data(as_text=True)

    # ARIA labels and interactive role are present on meal cells
    assert 'data-meal-cell' in html
    assert 'aria-label=' in html
    assert 'role="button"' in html

    # Unified badges for registration states
    assert 'registration-badge' in html
    assert 'yp-badge' in html


def test_weekview_no_legacy_inline_styles_leftovers(client_admin):
    app = client_admin.application
    site_id, dept_id = "site_p6_clean", "dept_p6_clean"
    _seed_site_and_department(app, site_id, dept_id)
    year, week = _current_year_week()

    r = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dept_id}&year={year}&week={week}",
        headers=_h("admin"),
    )
    assert r.status_code == 200
    html = r.get_data(as_text=True)

    # Specific inline styles we removed in Phase 6 should not appear
    assert 'font-size: 0.8rem; color: var(--color-text-muted);' not in html
    assert 'margin-top: 0.25rem;' not in html


def test_regression_other_views_still_work(client_admin):
    # Cook dashboard
    rc = client_admin.get('/ui/cook', headers=_h('cook'))
    assert rc.status_code == 200

    # Admin dashboard
    ra = client_admin.get('/ui/admin', headers=_h('admin'))
    assert ra.status_code == 200

    # Reports weekly
    from datetime import date as _d
    t = _d.today().isocalendar()
    ry = t[0]
    rw = t[1]
    rr = client_admin.get(f'/ui/reports/weekly?year={ry}&week={rw}', headers=_h('admin'))
    assert rr.status_code == 200
