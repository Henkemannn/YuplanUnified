import pytest
from core.app_factory import create_app
from core.db import get_session
from core.models import TenantFeatureFlag

@pytest.fixture
def app(client_admin):
    # client_admin fixture likely already created app; but build new minimal app if needed
    return client_admin.application


def test_feature_flag_flow(client_admin):
    app = client_admin.application
    # Ensure registry contains a sample flag
    flag_name = 'experimental_ui'

    # Initially not overridden -> enabled? fallback may be False if not in registry yet; we add via set
    resp = client_admin.post('/features/set', json={'name': flag_name, 'enabled': True}, headers={'X-User-Role':'admin','X-Tenant-Id':'1'})
    assert resp.status_code == 200
    assert resp.json['enabled'] is True

    # Verify via check endpoint
    resp = client_admin.get(f'/features/check?name={flag_name}', headers={'X-User-Role':'admin','X-Tenant-Id':'1'})
    assert resp.status_code == 200
    assert resp.json['enabled'] is True

    # Disable
    resp = client_admin.post('/features/set', json={'name': flag_name, 'enabled': False}, headers={'X-User-Role':'admin','X-Tenant-Id':'1'})
    assert resp.status_code == 200

    # Now check specific after disable
    resp = client_admin.get(f'/features/check?name={flag_name}', headers={'X-User-Role':'admin','X-Tenant-Id':'1'})
    assert resp.status_code == 200
    assert resp.json['enabled'] is False


def test_feature_flag_requires_tenant(client_admin, client_no_tenant):
    # No tenant context should fail setting a flag
    resp = client_no_tenant.post('/features/set', json={'name': 'abc', 'enabled': True}, headers={'X-User-Role':'admin'})
    assert resp.status_code == 400


def test_feature_flag_permissions(client_user):
    # Normal user should be forbidden
    resp = client_user.get('/features', headers={'X-User-Role':'user','X-Tenant-Id':'1'})
    assert resp.status_code in (401, 403)


def test_unknown_flag_defaults_false(client_admin):
    resp = client_admin.get('/features/check?name=__unknown__', headers={'X-User-Role':'admin','X-Tenant-Id':'1'})
    assert resp.status_code == 200
    assert resp.json['enabled'] is False
