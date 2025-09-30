import sys, os
import pytest

# Ensure project root on path BEFORE importing application modules
ROOT = os.path.dirname(__file__)
PARENT = os.path.abspath(os.path.join(ROOT, '..'))
if PARENT not in sys.path:
    sys.path.insert(0, PARENT)

from core.app_factory import create_app
from core.db import Base, init_engine, create_all
from core.models import TenantFeatureFlag, Tenant  # ensure model imported for metadata


@pytest.fixture(scope='session')
def app_session(tmp_path_factory):
    db_file = tmp_path_factory.mktemp('db') / 'test_app.db'
    url = f'sqlite:///{db_file}'
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test', 'database_url': url, 'FORCE_DB_REINIT': True})
    with app.app_context():
        create_all()
        # Seed a tenant with id=1
        from core.db import get_session
        db = get_session()
        try:
            if not db.query(Tenant).first():
                db.add(Tenant(name='TestTenant'))
                db.commit()
        finally:
            db.close()
    return app

@pytest.fixture
def client_admin(app_session):
    return app_session.test_client()

@pytest.fixture
def client_user(app_session):
    return app_session.test_client()

@pytest.fixture
def client_no_tenant(app_session):
    c = app_session.test_client()
    return c
