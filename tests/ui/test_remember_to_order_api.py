def test_remember_to_order_add_and_check_permissions(client_admin, client_cook):
    site_id = "site-remember"
    week_key = "2026-W08"

    with client_cook.session_transaction() as sess:
        sess["site_id"] = site_id
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id

    add_resp = client_cook.post(
        "/ui/api/remember-to-order/add",
        json={"site_id": site_id, "week_key": week_key, "text": "Bestall kaffe"},
        headers={"X-User-Role": "cook", "X-Tenant-Id": "1"},
    )
    assert add_resp.status_code == 200
    payload = add_resp.get_json() or {}
    item_id = payload.get("id")
    assert item_id

    check_resp = client_admin.post(
        "/ui/api/remember-to-order/check",
        json={"id": item_id, "checked": True},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert check_resp.status_code == 200

    allowed_for_cook = client_cook.post(
        "/ui/api/remember-to-order/check",
        json={"id": item_id, "checked": True},
        headers={"X-User-Role": "cook", "X-Tenant-Id": "1"},
    )
    assert allowed_for_cook.status_code == 200


def test_remember_to_order_check_blocks_cross_site_for_kitchen(client_cook):
    site_a = "site-remember-a"
    site_b = "site-remember-b"
    week_key = "2026-W08"

    with client_cook.session_transaction() as sess:
        sess["site_id"] = site_a

    add_resp = client_cook.post(
        "/ui/api/remember-to-order/add",
        json={"site_id": site_a, "week_key": week_key, "text": "Bestall flingor"},
        headers={"X-User-Role": "cook", "X-Tenant-Id": "1"},
    )
    assert add_resp.status_code == 200
    item_id = (add_resp.get_json() or {}).get("id")
    assert item_id

    with client_cook.session_transaction() as sess:
        sess["site_id"] = site_b

    check_resp = client_cook.post(
        "/ui/api/remember-to-order/check",
        json={"id": item_id, "checked": True},
        headers={"X-User-Role": "cook", "X-Tenant-Id": "1"},
    )
    assert check_resp.status_code == 404


def test_remember_to_order_add_allows_kitchen_role(client_user):
    site_id = "site-remember-kitchen"
    week_key = "2026-W08"

    with client_user.session_transaction() as sess:
        sess["site_id"] = site_id

    add_resp = client_user.post(
        "/ui/api/remember-to-order/add",
        json={"site_id": site_id, "week_key": week_key, "text": "Bestall brod"},
        headers={"X-User-Role": "kitchen", "X-Tenant-Id": "1", "X-User-Id": "8"},
    )

    assert add_resp.status_code == 200
    payload = add_resp.get_json() or {}
    assert payload.get("ok") is True
    assert payload.get("id")
