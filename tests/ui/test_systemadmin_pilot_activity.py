from __future__ import annotations

from sqlalchemy import text

from core.db import get_session
from core.models import Site, Tenant, User
from core.pilot_activity import track_activity


def _seed_superuser(db, tenant_id: int) -> User:
    user = db.query(User).filter(User.email == "pilot-sysadmin@example.com").first()
    if user:
        return user
    user = User(
        tenant_id=tenant_id,
        email="pilot-sysadmin@example.com",
        username="pilot-sysadmin",
        password_hash="x",
        role="superuser",
        is_active=True,
        unit_id=None,
        full_name="Pilot Admin",
    )
    db.add(user)
    db.commit()
    return user


def _seed_admin_user(db, tenant_id: int) -> User:
    user = db.query(User).filter(User.email == "pilot-admin@example.com").first()
    if user:
        return user
    user = User(
        tenant_id=tenant_id,
        email="pilot-admin@example.com",
        username="pilot-admin",
        password_hash="x",
        role="admin",
        is_active=True,
        unit_id=None,
        full_name="Anna Admin",
    )
    db.add(user)
    db.commit()
    return user


def test_systemadmin_dashboard_shows_pilot_activity(app_session):
    client = app_session.test_client()

    db = get_session()
    try:
        tenant = Tenant(name="Pilot Activity Tenant")
        db.add(tenant)
        db.commit()

        site = Site(id="pilot-site-activity-1", name="Pilot Site 1", tenant_id=tenant.id)
        db.add(site)
        db.commit()

        superuser = _seed_superuser(db, tenant.id)
        admin_user = _seed_admin_user(db, tenant.id)
        superuser_id = int(superuser.id)
        admin_user_id = int(admin_user.id)
        site_id = str(site.id)

        # Older event
        track_activity("open_weekview", user_id=admin_user_id, site_id=site_id)
        # Latest event
        track_activity("open_planera", user_id=admin_user_id, site_id=site_id)

        # Force deterministic latest event in case timestamps collide within same second.
        db.execute(
            text(
                """
                UPDATE pilot_activity_events
                SET created_at = datetime(created_at, '+1 second')
                WHERE site_id = :site_id AND event_type = 'open_planera'
                """
            ),
            {"site_id": site_id},
        )
        db.commit()

        with client.session_transaction() as sess:
            sess["user_id"] = superuser_id
            sess["role"] = "superuser"
            sess["tenant_id"] = tenant.id
    finally:
        db.close()

    rv = client.get("/ui/systemadmin/dashboard", follow_redirects=True)
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert "Pilot Activity" in html
    assert "Pilot Site 1" in html
    assert "Anna Admin" in html
    assert "open_planera" in html
