def test_weekview_openapi_included(client):
    res = client.get("/openapi.json")
    assert res.status_code == 200
    spec = res.get_json()
    # Tag present
    tags = [t.get("name") for t in spec.get("tags", [])]
    assert "weekview" in tags
    # Paths present
    paths = spec.get("paths", {})
    assert "/api/weekview" in paths
    assert "/api/weekview/resolve" in paths
