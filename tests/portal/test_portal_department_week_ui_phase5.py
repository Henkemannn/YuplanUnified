def test_portal_department_week_ui_phase5_conflict_modal_present(client_admin):
    year=2025; week=47
    dept_id="11111111-2222-3333-4444-555555555555"
    # Assumes seed script or existing data already created; just hit UI
    resp = client_admin.get(f"/ui/portal/department/week?year={year}&week={week}", environ_overrides={"test_claims": {"department_id": dept_id}})
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Modal structure present
    assert 'id="portal-conflict-overlay"' in html
    assert 'Informationen är utdaterad' in html
    # Action buttons now include refresh, reload, dismiss
    assert 'Försök igen' in html
    assert 'Ladda om' in html
    assert 'Fortsätt ändå' in html
