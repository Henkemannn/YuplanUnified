def test_spec_contains_notes_tasks_schemas(client_admin):
    spec = client_admin.get("/openapi.json", headers={"X-User-Role":"admin","X-Tenant-Id":"1"}).get_json()
    schemas = spec["components"]["schemas"]
    for name in ["Note","NoteCreate","Task","TaskCreate","TaskStatus"]:
        assert name in schemas
    assert "content" in schemas["Note"]["properties"]
    assert "title" in schemas["Task"]["properties"]
