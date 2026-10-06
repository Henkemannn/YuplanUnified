from __future__ import annotations

import uuid
import re
from pathlib import Path

from core.admin_repo import DepartmentServiceAddonsRepo, DepartmentsRepo, ServiceAddonsRepo, SitesRepo


def _h(role: str) -> dict[str, str]:
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def _set_site(client_admin, site_id: str) -> None:
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id


def _post_service_addon(
    client_admin,
    dept_id: str,
    *,
    mode: str = "add",
    addon_id: str = "",
    row_id: str = "",
    new_name: str = "",
    family: str = "ovrigt",
    family_custom: str = "",
    lunch: str = "",
    dinner: str = "",
    note: str = "",
    action: str = "",
) -> None:
    payload = {
        "service_addon_mode": mode,
        "service_addon_action": action,
        "service_addon_row_id": row_id,
        "service_addon_id": addon_id,
        "service_addon_new_name": new_name,
        "service_addon_family": family,
        "service_addon_family_custom": family_custom,
        "service_addon_lunch_count": lunch,
        "service_addon_dinner_count": dinner,
        "service_addon_note": note,
    }
    response = client_admin.post(
        f"/ui/admin/departments/{dept_id}/edit/service-addons",
        headers=_h("admin"),
        data=payload,
    )
    assert response.status_code in (302, 303)


def _addon_row(rows: list[dict], addon_name: str) -> dict:
    for row in rows:
        if row["addon_name"] == addon_name:
            return row
    raise AssertionError(f"missing addon row: {addon_name}")


def _state_block(html: str, state: str) -> str:
    match = re.search(
        rf'<section[^>]*class="admin-service-addon-modal__state"[^>]*data-service-addon-state="{state}"[^>]*>(.*?)</section>',
        html,
        re.S,
    )
    if not match:
        raise AssertionError(f"missing state block: {state}")
    return match.group(1)


def _dialog_block(html: str) -> str:
    match = re.search(r'<dialog id="service-addon-modal".*?</dialog>', html, re.S)
    if not match:
        raise AssertionError("missing service addon dialog")
    return match.group(0)


def _remove_form_block(html: str) -> str:
    match = re.search(r'<form[^>]*data-service-addon-remove-form[^>]*>.*?</form>', html, re.S)
    if not match:
        raise AssertionError("missing service addon remove form")
    return match.group(0)


def test_admin_department_service_addons_renders_compact_read_state_and_modal_contract(app_session, client_admin):
    site, _ = SitesRepo().create_site(f"Service addon site {uuid.uuid4()}")
    dep, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Service",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )

    addon_repo = ServiceAddonsRepo()
    mos_id = addon_repo.create_if_missing("Alltid mos vid kokt potatis", site_id=site["id"], addon_family="mos")
    sallad_id = addon_repo.create_if_missing("Sallad", site_id=site["id"], addon_family="sallad")
    extra_sas_id = addon_repo.create_if_missing("Extra sås", site_id=site["id"], addon_family="ovrigt")
    dessert_id = addon_repo.create_if_missing("Dessertsked", site_id=site["id"], addon_family="ovrigt")

    _set_site(client_admin, site["id"])
    _post_service_addon(client_admin, dep["id"], addon_id=mos_id, lunch="4")
    _post_service_addon(client_admin, dep["id"], addon_id=sallad_id, lunch="6", dinner="4", note="Aldrig tomat")
    _post_service_addon(client_admin, dep["id"], addon_id=extra_sas_id, dinner="3")
    _post_service_addon(client_admin, dep["id"], addon_id=dessert_id, lunch="2", dinner="1", note="Serveras separat")

    rv = client_admin.get(f"/ui/admin/departments/{dep['id']}/edit", headers=_h("admin"))
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)

    assert "Serveringsanpassningar" in html
    assert "+ Lägg till serveringsanpassning" in html
    assert "id=\"service-addon-modal\"" in html
    dialog_block = _dialog_block(html)
    assert dialog_block.count('data-service-addon-state="') == 4
    assert dialog_block.count('class="ua-modal-close"') == 1
    assert dialog_block.count('data-service-addon-remove-form') == 1
    assert 'data-service-addon-state="add"' in html
    assert 'data-service-addon-state="create"' in html
    assert 'data-service-addon-state="edit"' in html
    assert 'data-service-addon-state="remove"' in html
    assert 'data-service-addon-switch-create' in html
    assert 'data-service-addon-remove-start' in html
    assert 'data-service-addon-remove-confirm' in html
    assert '+ Skapa ny familj…' in html
    assert 'Välj befintlig' not in html
    assert 'Välj befintlig serveringsanpassning' not in html
    assert 'Lägg till en återkommande anpassning för avdelningen.' not in html
    js = Path('static/js/admin_service_addons.js').read_text(encoding='utf-8')
    assert js.count('Lägg till en återkommande anpassning för avdelningen.') == 1
    assert html.count('class="admin-service-addon-item"') == 4
    assert html.count('admin-service-addon-item__edit-trigger') == 4
    assert "Mos" in html
    assert "Lunch 4" in html
    assert "Sallad" in html
    assert "Lunch 6" in html
    assert "Kväll 4" in html
    assert "Övrigt" in html
    assert "Kväll 3" in html
    assert "Lunch 0" not in html
    assert "Kväll 0" not in html
    assert "Aldrig tomat" in html
    assert "Serveras separat" in html
    add_block = _state_block(html, "add")
    create_block = _state_block(html, "create")
    edit_block = _state_block(html, "edit")
    remove_block = _state_block(html, "remove")
    assert "Ta bort från avdelningen" not in add_block
    assert "Ta bort från avdelningen" not in create_block
    assert edit_block.count("Ta bort från avdelningen") == 1
    assert "Spara serveringsanpassning" not in remove_block
    assert "Lunch" not in remove_block
    assert "Kväll" not in remove_block
    assert "Notering" not in remove_block
    assert "Avbryt" in add_block
    assert "Avbryt" in create_block
    assert edit_block.count("Avbryt") == 1
    assert remove_block.count("Avbryt") == 1
    assert "data-service-addon-remove-start" not in create_block
    assert "data-service-addon-family-select" not in edit_block
    assert "data-service-addon-edit-family" in edit_block
    assert "Spara" not in remove_block
    assert "service_addon_new_name" not in add_block
    assert "service_addon_id" not in create_block
    assert "data-service-addon-remove-confirm" not in add_block
    remove_form = _remove_form_block(html)
    assert remove_form.count('data-service-addon-remove-confirm') == 1
    assert remove_form.count('data-service-addon-remove-cancel') == 1
    assert "Lunch" not in remove_form
    assert "Kväll" not in remove_form
    assert "Notering" not in remove_form
    assert "Spara" not in remove_form
    js_path = Path(__file__).resolve().parents[2] / 'static' / 'js' / 'admin_service_addons.js'
    js_text = js_path.read_text(encoding='utf-8')
    assert 'requestSubmit(' not in js_text
    assert '.submit(' not in js_text
    assert 'fetch(' not in js_text

    rows = DepartmentServiceAddonsRepo().list_for_department(dep["id"], site_id=site["id"])
    assert len(rows) == 4
    assert {"id", "department_id", "addon_id", "addon_name", "addon_family", "lunch_count", "dinner_count", "note"}.issubset(set(rows[0]))


def test_admin_department_service_addons_row_scoped_flow_preserves_siblings_and_catalog(app_session, client_admin):
    site, _ = SitesRepo().create_site(f"Service addon flow site {uuid.uuid4()}")
    dept_a, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Flow A",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    dept_b, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Flow B",
        resident_count_mode="fixed",
        resident_count_fixed=11,
    )

    addon_repo = ServiceAddonsRepo()
    mos_id = addon_repo.create_if_missing("Mos", site_id=site["id"], addon_family="mos")
    sallad_id = addon_repo.create_if_missing("Sallad", site_id=site["id"], addon_family="sallad")

    _set_site(client_admin, site["id"])
    _post_service_addon(client_admin, dept_a["id"], addon_id=mos_id, lunch="4")
    _post_service_addon(client_admin, dept_a["id"], addon_id=sallad_id, lunch="6", dinner="4", note="Aldrig tomat")
    _post_service_addon(client_admin, dept_a["id"], mode="create", new_name="Extra sås", family_custom="Sås", dinner="3", note="Såsen serveras separat")

    addon_rows = DepartmentServiceAddonsRepo().list_for_department(dept_a["id"], site_id=site["id"])
    assert len(addon_rows) == 3
    mos_row = _addon_row(addon_rows, "Mos")
    sallad_row = _addon_row(addon_rows, "Sallad")
    extra_row = _addon_row(addon_rows, "Extra sås")

    catalog_rows = {item["name"]: item for item in ServiceAddonsRepo().list_active(site["id"])}
    assert catalog_rows["Extra sås"]["addon_family"] == "Sås"
    assert catalog_rows["Mos"]["addon_family"] == "mos"

    _post_service_addon(
        client_admin,
        dept_a["id"],
        mode="edit",
        row_id=mos_row["id"],
        lunch="5",
        dinner="0",
        note="Lite mer mos",
    )

    addon_rows_after_edit = DepartmentServiceAddonsRepo().list_for_department(dept_a["id"], site_id=site["id"])
    assert len(addon_rows_after_edit) == 3
    assert _addon_row(addon_rows_after_edit, "Sallad")["dinner_count"] == 4
    assert _addon_row(addon_rows_after_edit, "Sallad")["note"] == "Aldrig tomat"
    assert _addon_row(addon_rows_after_edit, "Extra sås")["dinner_count"] == 3
    assert _addon_row(addon_rows_after_edit, "Mos")["lunch_count"] == 5
    assert _addon_row(addon_rows_after_edit, "Mos")["note"] == "Lite mer mos"
    catalog_rows = {item["name"]: item for item in ServiceAddonsRepo().list_active(site["id"])}
    assert catalog_rows["Mos"]["addon_family"] == "mos"
    assert catalog_rows["Sallad"]["addon_family"] == "sallad"
    assert catalog_rows["Extra sås"]["addon_family"] == "Sås"

    _post_service_addon(
        client_admin,
        dept_a["id"],
        action="remove",
        row_id=sallad_row["id"],
    )

    addon_rows_after_remove = DepartmentServiceAddonsRepo().list_for_department(dept_a["id"], site_id=site["id"])
    assert len(addon_rows_after_remove) == 2
    assert _addon_row(addon_rows_after_remove, "Mos")["lunch_count"] == 5
    assert _addon_row(addon_rows_after_remove, "Extra sås")["dinner_count"] == 3
    assert all(row["addon_name"] != "Sallad" for row in addon_rows_after_remove)
    catalog_rows_after_remove = {item["name"]: item for item in ServiceAddonsRepo().list_active(site["id"])}
    assert catalog_rows_after_remove["Sallad"]["addon_family"] == "sallad"

    _post_service_addon(client_admin, dept_b["id"], addon_id=mos_id, lunch="2")
    dept_b_rows = DepartmentServiceAddonsRepo().list_for_department(dept_b["id"], site_id=site["id"])
    assert len(dept_b_rows) == 1
    assert dept_b_rows[0]["addon_id"] == mos_row["addon_id"]

    rv = client_admin.get(f"/ui/admin/departments/{dept_a['id']}/edit", headers=_h("admin"))
    html = rv.get_data(as_text=True)
    assert "Redigera" in html
    assert "Ta bort från avdelningen" in html
    assert 'data-service-addon-row-id="' in html
    dialog_block = _dialog_block(html)
    assert dialog_block.count('class="ua-modal-close"') == 1
    assert dialog_block.count('data-service-addon-remove-form') == 1


def test_admin_department_service_addons_custom_family_and_quantity_cap(app_session, client_admin):
    site, _ = SitesRepo().create_site(f"Service addon family site {uuid.uuid4()}")
    dep, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Family",
        resident_count_mode="fixed",
        resident_count_fixed=12,
    )

    _set_site(client_admin, site["id"])
    _post_service_addon(
        client_admin,
        dep["id"],
        mode="create",
        new_name="Kall sås",
        family="__custom__",
        family_custom="Sås",
        lunch="12",
        dinner="0",
        note="Serveras kallt",
    )

    rows = DepartmentServiceAddonsRepo().list_for_department(dep["id"], site_id=site["id"])
    assert len(rows) == 1
    assert rows[0]["addon_name"] == "Kall sås"
    assert rows[0]["addon_family"] == "Sås"
    assert rows[0]["lunch_count"] == 12

    rv = client_admin.post(
        f"/ui/admin/departments/{dep['id']}/edit/service-addons",
        headers=_h("admin"),
        data={
            "service_addon_mode": "edit",
            "service_addon_row_id": rows[0]["id"],
            "service_addon_lunch_count": "13",
            "service_addon_dinner_count": "",
            "service_addon_note": "",
        },
        follow_redirects=True,
    )
    assert rv.status_code == 200
    assert "Antalet kan inte vara högre än avdelningens 12 boende." in rv.get_data(as_text=True)
    rows_after = DepartmentServiceAddonsRepo().list_for_department(dep["id"], site_id=site["id"])
    assert rows_after[0]["lunch_count"] == 12
    assert rows_after[0]["note"] == "Serveras kallt"

    addon_repo = ServiceAddonsRepo()
    extra_id = addon_repo.create_if_missing("Kall sås extra", site_id=site["id"], addon_family="Sås")
    reject_response = client_admin.post(
        f"/ui/admin/departments/{dep['id']}/edit/service-addons",
        headers=_h("admin"),
        data={
            "service_addon_mode": "add",
            "service_addon_id": extra_id,
            "service_addon_lunch_count": "13",
            "service_addon_dinner_count": "",
            "service_addon_note": "",
        },
        follow_redirects=True,
    )
    assert reject_response.status_code == 200
    assert "Antalet kan inte vara högre än avdelningens 12 boende." in reject_response.get_data(as_text=True)
    rows_after_reject = DepartmentServiceAddonsRepo().list_for_department(dep["id"], site_id=site["id"])
    assert len(rows_after_reject) == 1
    assert rows_after_reject[0]["lunch_count"] == 12

    rv_after = client_admin.get(f"/ui/admin/departments/{dep['id']}/edit", headers=_h("admin"))
    assert rv_after.status_code == 200
    html_after = rv_after.get_data(as_text=True)
    assert '<option value="sås">sås</option>' in html_after


def test_admin_department_service_addons_create_quantities_and_blank_validation(app_session, client_admin):
    site, _ = SitesRepo().create_site(f"Service addon create site {uuid.uuid4()}")
    dep, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Create",
        resident_count_mode="fixed",
        resident_count_fixed=12,
    )

    _set_site(client_admin, site["id"])

    _post_service_addon(
        client_admin,
        dep["id"],
        mode="create",
        new_name="Kall sallad",
        family="sallad",
        lunch="8",
        dinner="8",
        note="Säsongsanpassad",
    )
    rows = DepartmentServiceAddonsRepo().list_for_department(dep["id"], site_id=site["id"])
    assert len(rows) == 1
    assert rows[0]["addon_name"] == "Kall sallad"
    assert rows[0]["lunch_count"] == 8
    assert rows[0]["dinner_count"] == 8

    _post_service_addon(
        client_admin,
        dep["id"],
        mode="create",
        new_name="Morgonmos",
        family="mos",
        lunch="8",
        dinner="",
        note="Lunch only",
    )
    rows = DepartmentServiceAddonsRepo().list_for_department(dep["id"], site_id=site["id"])
    assert len(rows) == 2
    assert _addon_row(rows, "Morgonmos")["lunch_count"] == 8
    assert _addon_row(rows, "Morgonmos")["dinner_count"] is None

    _post_service_addon(
        client_admin,
        dep["id"],
        mode="create",
        new_name="Kvällssås",
        family="ovrigt",
        lunch="",
        dinner="8",
        note="Dinner only",
    )
    rows = DepartmentServiceAddonsRepo().list_for_department(dep["id"], site_id=site["id"])
    assert len(rows) == 3
    assert _addon_row(rows, "Kvällssås")["lunch_count"] is None
    assert _addon_row(rows, "Kvällssås")["dinner_count"] == 8

    rv = client_admin.post(
        f"/ui/admin/departments/{dep['id']}/edit/service-addons",
        headers=_h("admin"),
        data={
            "service_addon_mode": "create",
            "service_addon_new_name": "Blank",
            "service_addon_family": "ovrigt",
            "service_addon_lunch_count": "",
            "service_addon_dinner_count": "",
            "service_addon_note": "",
        },
        follow_redirects=True,
    )
    assert rv.status_code == 200
    assert "Antalet måste vara större än 0 för minst en måltid." in rv.get_data(as_text=True)
    rows_after_reject = DepartmentServiceAddonsRepo().list_for_department(dep["id"], site_id=site["id"])
    assert len(rows_after_reject) == 3


def test_admin_department_service_addons_zero_count_rejected_and_site_isolated(app_session, client_admin):
    site_a, _ = SitesRepo().create_site(f"Service addon site A {uuid.uuid4()}")
    site_b, _ = SitesRepo().create_site(f"Service addon site B {uuid.uuid4()}")

    dept_a, _ = DepartmentsRepo().create_department(
        site_id=site_a["id"],
        name="Avd Site A",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    dept_b, _ = DepartmentsRepo().create_department(
        site_id=site_b["id"],
        name="Avd Site B",
        resident_count_mode="fixed",
        resident_count_fixed=11,
    )

    addon_repo = ServiceAddonsRepo()
    addon_a = addon_repo.create_if_missing("A-Mos", site_id=site_a["id"], addon_family="mos")
    addon_b = addon_repo.create_if_missing("B-Sallad", site_id=site_b["id"], addon_family="sallad")

    _set_site(client_admin, site_a["id"])

    before_rows = DepartmentServiceAddonsRepo().list_for_department(dept_a["id"], site_id=site_a["id"])
    _post_service_addon(client_admin, dept_a["id"], addon_id=addon_a, lunch="0", dinner="0")
    after_zero_rows = DepartmentServiceAddonsRepo().list_for_department(dept_a["id"], site_id=site_a["id"])
    assert after_zero_rows == before_rows

    _post_service_addon(client_admin, dept_a["id"], addon_id=addon_a, lunch="3")
    rows_after_add = DepartmentServiceAddonsRepo().list_for_department(dept_a["id"], site_id=site_a["id"])
    assert len(rows_after_add) == 1

    rv = client_admin.get(f"/ui/admin/departments/{dept_a['id']}/edit", headers=_h("admin"))
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert "B-Sallad" not in html

    _post_service_addon(
        client_admin,
        dept_a["id"],
        addon_id=addon_b,
        lunch="3",
    )
    assert DepartmentServiceAddonsRepo().list_for_department(dept_a["id"], site_id=site_a["id"]) == rows_after_add
    assert DepartmentServiceAddonsRepo().list_for_department(dept_b["id"], site_id=site_b["id"]) == []
