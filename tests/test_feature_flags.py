import pytest

from core.feature_flags import FeatureRegistry, FlagDefinition


@pytest.fixture
def app(client_admin):
    # client_admin fixture likely already created app; but build new minimal app if needed
    return client_admin.application


def test_feature_flag_flow(client_admin):
    # app variable unused; rely on client_admin directly
    # Ensure registry contains a sample flag
    flag_name = "experimental_ui"

    # Initially not overridden -> enabled? fallback may be False if not in registry yet; we add via set
    resp = client_admin.post("/features/set", json={"name": flag_name, "enabled": True}, headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    assert resp.status_code == 200
    assert resp.json["enabled"] is True

    # Verify via check endpoint
    resp = client_admin.get(f"/features/check?name={flag_name}", headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    assert resp.status_code == 200
    assert resp.json["enabled"] is True

    # Disable
    resp = client_admin.post("/features/set", json={"name": flag_name, "enabled": False}, headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    assert resp.status_code == 200

    # Now check specific after disable
    resp = client_admin.get(f"/features/check?name={flag_name}", headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    assert resp.status_code == 200
    assert resp.json["enabled"] is False


def test_feature_flag_requires_tenant(client_admin, client_no_tenant):
    # No tenant context should fail setting a flag
    resp = client_no_tenant.post("/features/set", json={"name": "abc", "enabled": True}, headers={"X-User-Role":"admin"})
    # Updated expectation: with role but no tenant, session considered incomplete -> 401
    assert resp.status_code == 401


def test_feature_flag_permissions(client_user):
    # Normal user should be forbidden
    resp = client_user.get("/features", headers={"X-User-Role":"user","X-Tenant-Id":"1"})
    assert resp.status_code in (401, 403)


def test_unknown_flag_defaults_false(client_admin):
    resp = client_admin.get("/features/check?name=__unknown__", headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    assert resp.status_code == 200
    assert resp.json["enabled"] is False


def test_seed_flags_enabled():
    reg = FeatureRegistry()
    # pick a few known seeds
    assert reg.enabled("menus")
    assert reg.enabled("diet")


def test_add_new_flag_idempotent():
    reg = FeatureRegistry(seed=())
    definition: FlagDefinition = {"name": "alpha", "mode": "simple"}
    reg.add(definition)
    assert reg.enabled("alpha")
    # second add does not change or error
    reg.add(definition)
    assert reg.enabled("alpha")


def test_add_empty_name_rejected():
    reg = FeatureRegistry(seed=())
    with pytest.raises(ValueError):
        reg.add({"name": "", "mode": "simple"})


def test_set_unknown_flag_rejected():
    reg = FeatureRegistry(seed=())
    with pytest.raises(ValueError):
        reg.set("nope", True)


def test_disable_and_enable_cycle():
    reg = FeatureRegistry()
    assert reg.enabled("menus")
    reg.set("menus", False)
    assert not reg.enabled("menus")
    reg.set("menus", True)
    assert reg.enabled("menus")


def test_list_sorted_and_modes_preserved():
    reg = FeatureRegistry(seed=())
    reg.add({"name": "b_flag", "mode": "simple"})
    reg.add({"name": "a_flag", "mode": "simple"})
    names = [f["name"] for f in reg.list()]
    assert names == sorted(names)
    for f in reg.list():
        assert f["mode"] == "simple"
