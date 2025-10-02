import uuid

from core import create_app
from core.models import Base


def make_app(tmp_path, name="test"):
    db_url = f"sqlite:///{tmp_path}/{name}.db"
    # Reset global engine/session so each test isolates state
    from core import db as core_db  # type: ignore
    core_db._engine = None  # type: ignore
    core_db._SessionFactory = None  # type: ignore
    app = create_app({"database_url": db_url, "secret_key": "test"})
    # Initialize engine explicitly then create schema
    engine = core_db.init_engine(db_url)  # type: ignore
    Base.metadata.create_all(engine)
    return app

def auth_superuser(client, app):
    from werkzeug.security import generate_password_hash

    from core.db import get_session
    from core.models import Tenant, User
    db = get_session()
    try:
        t = Tenant(name="T1_" + uuid.uuid4().hex[:8])
        db.add(t); db.flush(); tid = t.id
        u = User(tenant_id=tid, email="root@example.com", password_hash=generate_password_hash("pw"), role="superuser", unit_id=None)
        db.add(u); db.commit()
    finally:
        db.close()
    rv = client.post("/auth/login", json={"email":"root@example.com","password":"pw"})
    assert rv.status_code==200
    return tid

def test_diet_type_crud_and_feature_toggle(tmp_path):
    app = make_app(tmp_path, name="diet")
    with app.test_client() as client:
        auth_superuser(client, app)
        # Create tenant via admin API (with modules triggers feature seeding) - reuse existing superuser context
        rv = client.post("/admin/tenants", json={
            "name": "MunicipalX","modules":["municipal"],"admin_email":"a@b.c","admin_password":"pw"
        })
        assert rv.status_code==200
        new_tid = rv.get_json()["tenant_id"]
        # Toggle a feature off then on
        rv = client.post("/admin/features/toggle", json={"feature":"menus","enabled":False,"tenant_id":new_tid})
        assert rv.status_code==200 and rv.get_json()["enabled"] is False
        rv = client.post("/admin/features/toggle", json={"feature":"menus","enabled":True,"tenant_id":new_tid})
        assert rv.status_code==200 and rv.get_json()["enabled"] is True
        # Login as the created admin to test diet CRUD
        rv = client.post("/auth/login", json={"email":"a@b.c","password":"pw"})
        assert rv.status_code==200
        # Create diet type
        rv = client.post("/diet/types", json={"name":"Glutenfri","default_select":True})
        assert rv.status_code==200
        diet_id = rv.get_json()["diet_type_id"]
        # List
        rv = client.get("/diet/types")
        types = rv.get_json()["diet_types"]
        assert any(t["id"]==diet_id and t["default_select"] for t in types)
        # Update
        rv = client.post(f"/diet/types/{diet_id}", json={"name":"Glutenfri Uppd","default_select":False})
        assert rv.status_code==200
        rv = client.get("/diet/types")
        types = rv.get_json()["diet_types"]
        assert any(t["id"]==diet_id and t["name"]=="Glutenfri Uppd" and (not t["default_select"]) for t in types)
        # Delete
    rv = client.delete(f"/diet/types/{diet_id}")
    assert rv.status_code==200
    rv = client.get("/diet/types")
    assert diet_id not in [t["id"] for t in rv.get_json()["diet_types"]]

def test_service_metrics_ingest_and_summary(tmp_path):
    app = make_app(tmp_path, name="metrics")
    with app.test_client() as client:
        tenant_id = auth_superuser(client, app)
        # Need a unit to attach metrics -> create directly
        from core.db import get_session
        from core.models import Unit
        db = get_session()
        try:
            unit = Unit(tenant_id=tenant_id, name="U1", default_attendance=10)
            db.add(unit); db.commit(); db.refresh(unit); unit_id=unit.id
        finally:
            db.close()
        # Ingest metrics rows
        rows = [
            {"unit_id":unit_id,"date":"2025-09-28","meal":"lunch","category":"main","guest_count":10,"produced_qty_kg":5.0,"served_qty_kg":4.0,"leftover_qty_kg":1.0},
            {"unit_id":unit_id,"date":"2025-09-28","meal":"lunch","category":"dessert","guest_count":10,"produced_qty_kg":2.0,"served_qty_kg":1.5,"leftover_qty_kg":0.5},
        ]
        rv = client.post("/metrics/ingest", json={"rows": rows})
        assert rv.status_code==200
        body = rv.get_json()
        assert body["inserted"]==2
        # Re-ingest modified row for main (update path)
        rows[0]["served_qty_kg"]=4.2
        rv = client.post("/metrics/ingest", json={"rows": [rows[0]]})
        body = rv.get_json(); assert body["updated"]==1
        # Query
        rv = client.post("/metrics/query", json={"filters": {"date_from":"2025-09-28","date_to":"2025-09-28"}})
        data = rv.get_json()["rows"]
        assert len(data)==2
        # Summary
        rv = client.get("/metrics/summary/day?from=2025-09-28&to=2025-09-28")
        summ = rv.get_json()["rows"]
        assert len(summ)==1  # grouped by meal/unit/date
        row = summ[0]
    assert row["produced_qty_kg"]==7.0 and row["served_qty_kg"]==5.7 and row["leftover_qty_kg"]==1.5