import os
import sys

import pytest

# Path setup before any project imports to satisfy E402
ROOT = os.path.dirname(__file__)
PARENT = os.path.abspath(os.path.join(ROOT, ".."))
if PARENT not in sys.path:  # pragma: no cover - environment dependent
    sys.path.insert(0, PARENT)

def _lazy_imports():  # isolate heavy imports & satisfy lint ordering
    from core.app_factory import create_app  # noqa: E402
    from core.db import create_all  # noqa: E402
    from core.models import Tenant  # noqa: E402
    return create_app, create_all, Tenant


@pytest.fixture(scope="session")
def app_session(tmp_path_factory):
    create_app, create_all, Tenant = _lazy_imports()
    db_file = tmp_path_factory.mktemp("db") / "test_app.db"
    url = f"sqlite:///{db_file}"
    app = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": url, "FORCE_DB_REINIT": True})
    with app.app_context():
        create_all()
        # Seed a tenant with id=1
        from core.db import get_session
        db = get_session()
        try:
            if not db.query(Tenant).first():
                db.add(Tenant(name="TestTenant"))
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
