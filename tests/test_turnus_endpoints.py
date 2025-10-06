from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

from core.app_factory import create_app
from core.db import get_session
from core.models import Tenant, Unit, User


def _bootstrap_admin(db):
    import uuid
    t = Tenant(name="TurnusT_" + uuid.uuid4().hex[:5])
    db.add(t); db.flush()
    unit = Unit(tenant_id=t.id, name="U1")
    db.add(unit); db.flush()
    user = User(tenant_id=t.id, email=f"admin_{uuid.uuid4().hex[:6]}@ex.com", password_hash=generate_password_hash("pw"), role="admin", unit_id=unit.id)
    db.add(user); db.commit()
    return t, user, unit


def _login(client, email):
    r = client.post("/auth/login", json={"email": email, "password": "pw"})
    assert r.status_code == 200


def test_turnus_templates_and_import_and_query():
    app = create_app({"TESTING": True, "SECRET_KEY": "x"})
    client = app.test_client()
    db = get_session()
    t, user, unit = _bootstrap_admin(db)
    user_email = user.email  # capture before session close
    unit_id = unit.id
    db.close()

    _login(client, user_email)

    # Create template
    r = client.post("/turnus/templates", json={"name": "Week Base", "pattern_type": "weekly"})
    assert r.status_code == 200
    tpl_id = r.get_json()["id"]
    # Duplicate create returns same id
    r2 = client.post("/turnus/templates", json={"name": "Week Base", "pattern_type": "weekly"})
    assert r2.get_json()["id"] == tpl_id

    # Import shifts (two distinct + one duplicate + one invalid end before start)
    start0 = datetime(2025, 10, 1, 8, 0)
    payload = {
        "template_id": tpl_id,
        "shifts": [
            {"unit_id": unit_id, "start_ts": start0.isoformat(timespec="minutes"), "end_ts": (start0 + timedelta(hours=4)).isoformat(timespec="minutes"), "role": "cook"},
            {"unit_id": unit_id, "start_ts": (start0 + timedelta(hours=5)).isoformat(timespec="minutes"), "end_ts": (start0 + timedelta(hours=9)).isoformat(timespec="minutes"), "role": "cook"},
            {"unit_id": unit_id, "start_ts": start0.isoformat(timespec="minutes"), "end_ts": (start0 + timedelta(hours=4)).isoformat(timespec="minutes"), "role": "cook"},  # duplicate
            {"unit_id": unit_id, "start_ts": (start0 + timedelta(hours=10)).isoformat(timespec="minutes"), "end_ts": (start0 + timedelta(hours=9)).isoformat(timespec="minutes"), "role": "cook"},  # invalid
        ]
    }
    r = client.post("/turnus/import", json=payload)
    data = r.get_json()
    if data["inserted"] != 2 or data["skipped"] != 2:
        print("DEBUG import result", data)
        # fetch slots directly
        r_slots_dbg = client.get("/turnus/slots", query_string={"from": "2025-10-01", "to": "2025-10-01"})
        print("DEBUG slots", r_slots_dbg.get_json())
    assert data["inserted"] == 2
    assert data["skipped"] == 2

    # Query slots - full day
    r = client.get("/turnus/slots", query_string={"from": "2025-10-01", "to": "2025-10-01"})
    slots = r.get_json()
    assert len(slots) == 2
    # Filter by role
    r = client.get("/turnus/slots", query_string={"from": "2025-10-01", "to": "2025-10-01", "role": "cook"})
    assert len(r.get_json()) == 2
    # Filter non-existent role
    r = client.get("/turnus/slots", query_string={"from": "2025-10-01", "to": "2025-10-01", "role": "driver"})
    assert r.get_json() == []