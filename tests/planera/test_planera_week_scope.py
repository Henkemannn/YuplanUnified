import uuid

import pytest
from sqlalchemy import text

from core.db import get_session
from tests._auth_site_helpers import login_bound_user


@pytest.mark.parametrize("endpoint", ["/api/planera/week", "/api/planera/week/csv"])
@pytest.mark.parametrize("tenant_id", [1, 2])
@pytest.mark.parametrize("site_lock", [True, False, None])
def test_planera_week_rejects_site_id_outside_authenticated_scope(
    client_admin,
    endpoint: str,
    tenant_id: int,
    site_lock: bool | None,
) -> None:
    app = client_admin.application
    bound_site = str(uuid.uuid4())
    requested_site = str(uuid.uuid4())
    year, week = 2026, 48

    with app.app_context():
        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT INTO sites(id, name, tenant_id, version) "
                    "VALUES(:bound_id, 'Bound site', 1, 0), "
                    "(:requested_id, 'Requested site', :requested_tenant, 0)"
                ),
                {
                    "bound_id": bound_site,
                    "requested_id": requested_site,
                    "requested_tenant": tenant_id,
                },
            )
            db.commit()
        finally:
            db.close()
        registry = getattr(app, "feature_registry", None)
        if registry is not None:
            if not registry.has("ff.planera.enabled"):
                registry.add("ff.planera.enabled")
            registry.set("ff.planera.enabled", True)

    login_bound_user(client_admin, site_id=bound_site, role="admin")
    with client_admin.session_transaction() as session:
        if site_lock is None:
            session.pop("site_lock", None)
        else:
            session["site_lock"] = site_lock

    response = client_admin.get(
        f"{endpoint}?site_id={requested_site}&year={year}&week={week}"
    )

    assert response.status_code == 404
    assert "Requested site" not in response.get_data(as_text=True)
