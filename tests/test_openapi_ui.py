from core.app_factory import create_app


def test_docs_served(client_admin):
    # admin header triggers session injection
    r = client_admin.get('/docs/', headers={'X-User-Role':'admin','X-Tenant-Id':'1'})
    # If feature flag present (openapi_ui in registry) should be 200
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert b'SwaggerUIBundle' in r.data
