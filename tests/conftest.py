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


# -------------------------------
# CSRF gradual-hardening support
# -------------------------------
# We introduce a marker ``csrf_legacy`` that is auto-applied to (almost) every
# test so that a STRICT_CSRF_IN_TESTS job can run only the already-migrated
# tests with ``-m 'not csrf_legacy'``. As individual tests are updated to send a
# CSRF header they should explicitly add ``@pytest.mark.usefixtures('csrf_headers')``
# OR request the ``csrf_headers`` fixture in their parameter list and (optionally)
# remove the legacy marker (or we eventually delete the auto-marking logic).
# The allowlist below enumerates tests that already exercise CSRF semantics or
# intentionally validate behavior without a token; they must not receive the
# legacy marker so they participate in the strict subset from day one.

_CSRF_ALLOWLIST_FILES = {
    "test_csrf_prod.py",
    "test_cookies.py",
}


def pytest_configure(config):  # pragma: no cover - pytest hook
    config.addinivalue_line(
        "markers",
        "csrf_legacy: test has NOT been migrated to send CSRF token; excluded in strict job",
    )


def pytest_collection_modifyitems(config, items):  # pragma: no cover - collection time
    # Auto-tag every test not in allowlist so the strict job can exclude them.
    for item in items:
        filename = os.path.basename(item.location[0])
        if filename in _CSRF_ALLOWLIST_FILES:
            continue
        # Don't double-mark if user already opted out manually.
        if not any(m.name == "csrf_legacy" for m in item.own_markers):
            item.add_marker(pytest.mark.csrf_legacy)


@pytest.fixture
def csrf_headers(client):
    """Return headers containing a valid CSRF token (double-submit pattern).

    Strategy: perform one or more safe GETs until server issues the csrf_token cookie,
    then mirror it in X-CSRF-Token header. Robust across differing public endpoints
    (health/metrics/openapi/root). Fails fast with an assertion if cookie missing.
    """
    # Candidate public GET endpoints (some may not exist in all environments)
    candidates = ["/health", "/metrics", "/openapi.json", "/"]
    token = None
    for path in candidates:
        client.get(path)
        for c in getattr(client, "cookie_jar", []):  # werkzeug test client cookie jar
            if c.name == "csrf_token":
                token = c.value
                break
        if token:
            break
    assert token, "csrf_token saknas i cookies efter försök på: {}".format(", ".join(candidates))
    return {"X-CSRF-Token": token}


@pytest.fixture(scope="session")
def app_session(tmp_path_factory):
    create_app, create_all, Tenant = _lazy_imports()
    db_file = tmp_path_factory.mktemp("db") / "test_app.db"
    url = f"sqlite:///{db_file}"
    app = create_app(
        {"TESTING": True, "SECRET_KEY": "test", "database_url": url, "FORCE_DB_REINIT": True}
    )
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
def client_superuser(app_session):
    return app_session.test_client()


@pytest.fixture
def client_no_tenant(app_session):
    c = app_session.test_client()
    return c


@pytest.fixture
def client(client_admin):
    """Alias fixture expected by some tests (e.g., OpenAPI tests) mapping to admin client.
    Keeps backward compatibility with existing role-based fixtures while avoiding duplication.
    """
    return client_admin
