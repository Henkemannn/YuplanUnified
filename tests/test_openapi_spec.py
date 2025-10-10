

def test_openapi_basic_structure(client_admin):
    r = client_admin.get("/openapi.json", headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    assert r.status_code == 200
    spec = r.get_json()
    assert spec["openapi"].startswith("3.")
    # Ensure core tags present
    tag_names = {t["name"] for t in spec.get("tags", [])}
    for expected in {"Auth","Menus","Features","System"}:
        assert expected in tag_names
    # Basic path presence
    for p in ["/features","/features/check","/features/set"]:
        assert p in spec["paths"]


def test_features_paths_documented_methods(client_admin):
    spec = client_admin.get("/openapi.json", headers={"X-User-Role":"admin","X-Tenant-Id":"1"}).get_json()
    features_check = spec["paths"]["/features/check"]
    assert "get" in features_check or "GET" in features_check
    # description string mention enabled=false for unknown
    get_obj = features_check.get("get") or features_check.get("GET")
    assert "unknown -> enabled=false" in (get_obj.get("responses", {}).get("200", {}).get("description",""))


def test_problem_schema_fields(client_admin):
    spec = client_admin.get("/openapi.json", headers={"X-User-Role":"admin","X-Tenant-Id":"1"}).get_json()
    pd = spec["components"]["schemas"]["ProblemDetails"]
    assert all(k in pd["properties"] for k in ("type","title","status","detail","request_id"))


def test_paths_reference_error_responses(client_admin):
    spec = client_admin.get("/openapi.json", headers={"X-User-Role":"admin","X-Tenant-Id":"1"}).get_json()
    # representative subset
    subset = ["/notes/","/tasks/","/features","/features/check"]
    for path in subset:
        ops = spec["paths"][path]
        for method_def in ops.values():
            responses = method_def["responses"]
            assert "500" in responses
            if path in ("/notes/","/tasks/","/features/check"):
                # 400 should be present for validation contexts
                assert "400" in responses
