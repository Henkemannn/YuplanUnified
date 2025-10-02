def test_openapi_basic(client):
    res = client.get("/openapi.json")
    assert res.status_code == 200
    data = res.get_json()
    assert data and data.get("openapi") == "3.0.3"
    assert "paths" in data and len(data["paths"]) > 0
    # Ensure core domains present
    for p in ["/features", "/notes/", "/tasks/"]:
        assert any(k.startswith(p) or k == p for k in data["paths"]), f"missing path {p}"


def test_openapi_error_components(client):
    res = client.get("/openapi.json")
    spec = res.get_json()
    comps = spec["components"]
    assert "schemas" in comps and "Error" in comps["schemas"]
    assert "responses" in comps and "Error403" in comps["responses"]
    # Check enriched forbidden example includes required_role
    forbidden = comps["responses"]["Error403"]["content"]["application/json"]["examples"]["forbidden"]["value"]
    assert "required_role" in forbidden
