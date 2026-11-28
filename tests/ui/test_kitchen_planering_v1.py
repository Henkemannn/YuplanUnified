import pytest
import uuid
from sqlalchemy import text
from html.parser import HTMLParser

from core.admin_repo import DepartmentServiceAddonsRepo, DepartmentsRepo, ServiceAddonsRepo

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


class _IdParentParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._stack = []
        self.parents = {}

    def handle_starttag(self, tag, attrs):
        attrs_d = {k: v for k, v in attrs}
        node_id = attrs_d.get("id")
        parent_ids = [sid for sid in self._stack if sid]
        if node_id:
            self.parents[node_id] = list(parent_ids)
        self._stack.append(node_id)

    def handle_endtag(self, tag):
        if self._stack:
            self._stack.pop()


def _seed_basics():
    from core.db import get_session

    site_id = str(uuid.uuid4())
    conn = get_session()
    try:
        conn.execute(
            text("INSERT INTO sites (id, tenant_id, name) VALUES (:id, 1, :name)"),
            {"id": site_id, "name": f"Planera V1 {uuid.uuid4()}"},
        )
        conn.commit()
    finally:
        conn.close()
    return site_id


def test_planering_v1_empty_state(app_session):
    client = app_session.test_client()
    site_id = _seed_basics()
    rv = client.get(f"/ui/kitchen/planering?site_id={site_id}", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert "Välj dag och måltid" in html


def test_planering_v1_selected_state(app_session):
    client = app_session.test_client()
    site_id = _seed_basics()
    # Seed a department and a diet type with defaults so the checklist has options
    from core.admin_repo import DepartmentsRepo, DietTypesRepo

    drepo = DepartmentsRepo()
    dep, _version = drepo.create_department(
        site_id=site_id,
        name="Avd 1",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    trepo = DietTypesRepo()
    dt_name = f"Glutenfri-{uuid.uuid4().hex[:8]}"
    dt_id = trepo.create(
        site_id=site_id,
        tenant_id=1,
        name=dt_name,
        default_select=False,
    )
    assert dep["site_id"] == site_id
    ver = drepo.get_version(dep["id"]) or 0
    drepo.upsert_department_diet_defaults(dep["id"], ver, [{"diet_type_id": str(dt_id), "default_count": 3}])

    from tests._auth_site_helpers import login_bound_user

    login_bound_user(client, site_id=site_id)

    # First request: selected day+meal should render checklist UI immediately (wizard step 3)
    rv = client.get(f"/ui/kitchen/planering?site_id={site_id}&day=0&meal=lunch")
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert "Rätt:" not in html
    assert "Header" not in html
    assert "Specialkoster" in html
    assert "Resultatsammanfattning" in html
    assert 'id="kp-what-alt1"' in html
    assert 'id="kp-what-alt2"' in html
    assert "Specialkost – arbetslista" in html
    assert "js-special-chip" in html
    assert "data-diet-id" in html
    assert "Välj specialkoster ovan för att bygga arbetslistan." in html
    assert f"/ui/production-lists?site_id={site_id}" in html

    # Second request: with a selected diet, adaptation list should render
    rv2 = client.get(f"/ui/kitchen/planering?site_id={site_id}&day=0&meal=lunch&selected_diets={dt_id}")
    assert rv2.status_code == 200
    html2 = rv2.data.decode("utf-8")
    assert "Specialkost – arbetslista" in html2
    assert "Avd 1" in html2

    # Normal mode still presents result totals and department table.
    rv3 = client.get(f"/ui/kitchen/planering?site_id={site_id}&day=0&meal=lunch&mode=normal")
    assert rv3.status_code == 200
    html3 = rv3.data.decode("utf-8")
    assert "Resultat" in html3
    assert "Visa per avdelning" in html3
    assert "Avdelning" in html3
    assert 'id="kp-total-alt1"' in html3
    assert 'id="kp-total-alt2"' in html3


def test_planering_modals_are_separate_and_controls_present(app_session):
    client = app_session.test_client()
    site_id = _seed_basics()

    rv = client.get(f"/ui/kitchen/planering?site_id={site_id}&day=0&meal=lunch", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")

    assert 'class="kp-button kp-button-primary js-open-production-list-modal"' in html
    assert 'class="kp-button js-open-dept-summary"' in html
    assert 'id="production-list-modal"' in html
    assert 'id="dept-summary-modal"' in html

    parser = _IdParentParser()
    parser.feed(html)
    prod_parents = parser.parents.get("production-list-modal", [])
    assert "dept-summary-modal" not in prod_parents


def test_planering_js_modal_wiring_contract():
    from pathlib import Path

    js = Path("static/ui/kitchen_planering_v1.js").read_text(encoding="utf-8")
    assert "var btn = qs('.js-open-dept-summary');" in js
    assert "var modal = qs('#dept-summary-modal');" in js
    assert "var openBtn = qs('.js-open-production-list-modal');" in js
    assert "var modal = qs('#production-list-modal');" in js


def test_planering_template_has_serveringstillbehor_tab_and_no_addon_dropdown():
    from pathlib import Path

    tpl = Path("templates/ui/kitchen_planering_v1.html").read_text(encoding="utf-8")

    assert 'data-plan-tab="planera"' in tpl
    assert 'data-plan-tab="service-addons"' in tpl
    assert "Serveringstillbehör" in tpl
    assert "('mos', 'MOS')" in tpl
    assert "('sallad', 'SALLAD')" in tpl
    assert "('ovrigt', 'ÖVRIGT')" in tpl
    assert '<h2 class="kp-section-title">Serveringstillbehör</h2>' in tpl
    assert '<h3>Serveringstillbehör</h3>' not in tpl
    assert 'Ingen data för {{ family_label }}.' not in tpl
    assert 'Inga serveringstillbehör registrerade.' in tpl
    assert 'data-mode="normal-alt1"' in tpl
    assert 'data-mode="normal-alt2"' in tpl
    assert 'data-mode="normal-single"' in tpl
    assert "Valt tillägg" not in tpl


def test_planering_print_is_scoped_to_active_tab_contract():
    from pathlib import Path

    js = Path("static/ui/kitchen_planering_v1.js").read_text(encoding="utf-8")

    assert "function getActivePlanTabName()" in js
    assert "if(activePlanTab === 'service-addons')" in js
    assert "function groupAddonsByFamily(addons)" in js
    assert "{ key: 'mos', title: 'MOS' }" in js
    assert "{ key: 'sallad', title: 'SALLAD' }" in js
    assert "{ key: 'ovrigt', title: 'ÖVRIGT' }" in js


def test_planering_print_row_order_and_plain_alt_text_contract():
    from pathlib import Path

    js = Path("static/ui/kitchen_planering_v1.js").read_text(encoding="utf-8")
    css = Path("static/css/kitchen_planering_print.css").read_text(encoding="utf-8")

    assert '<span class="kp-dept-name">' in js
    assert '<span class="count">' in js
    assert '<span class="kp-print-alt-text">' in js
    assert "Alt 1" in js
    assert "Alt 2" in js
    assert "grid-template-columns: minmax(0, 1fr) 64px 64px;" in css
    assert "border-left: 1px solid #dbe4f0;" in css


def test_planering_print_reduces_specialkost_duplicate_variant_lines_contract():
    from pathlib import Path

    js = Path("static/ui/kitchen_planering_v1.js").read_text(encoding="utf-8")

    assert "function buildVariantSummaryLine(groupName, variants, total)" in js
    assert "function displayGroupLabel(name)" in js
    assert "variantSummary" in js


def test_planering_dessert_hides_service_addons_summary(app_session):
    client = app_session.test_client()
    site_id = _seed_basics()

    dep, _ = DepartmentsRepo().create_department(
        site_id=site_id,
        name="Avd Dessert",
        resident_count_mode="fixed",
        resident_count_fixed=8,
    )

    addon_id = ServiceAddonsRepo().create_if_missing("Mos", site_id=site_id, addon_family="mos")
    DepartmentServiceAddonsRepo().replace_for_department(
        dep["id"],
        [{"addon_id": addon_id, "lunch_count": 5, "dinner_count": 0, "note": ""}],
        site_id=site_id,
    )

    rv = client.get(
        f"/ui/kitchen/planering?site_id={site_id}&mode=normal&day=0&meal=dessert",
        headers=HEADERS,
    )
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert "data-service-addons-summary='[]'" in html
