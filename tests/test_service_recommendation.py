from datetime import date, timedelta

import pytest
from flask import Flask
from werkzeug.security import generate_password_hash

from core.app_factory import create_app
from core.db import get_session
from core.models import PortionGuideline, ServiceMetric, Tenant, User


@pytest.fixture()
def app():
    return create_app({"TESTING": True, "SECRET_KEY": "test"})


@pytest.fixture()
def client(app: Flask):
    return app.test_client()


@pytest.fixture()
def setup_tenant():
    """Ensure isolated baseline context per test.
    Clears existing metrics / guidelines / user with same email to avoid leakage across tests
    since we reuse same SQLite file in process.
    """
    db = get_session()
    try:
        tenant = db.query(Tenant).first()
        if not tenant:
            tenant = Tenant(name="PortionTest")
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
        # Clean previous test artifacts
        db.query(ServiceMetric).delete()
        db.query(PortionGuideline).delete()
        db.query(User).filter(User.email == "portion_admin@example.com").delete()
        db.commit()
        user = User(
            tenant_id=tenant.id,
            email="portion_admin@example.com",
            password_hash=generate_password_hash("pw"),
            role="admin",
            unit_id=None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        guideline = PortionGuideline(
            tenant_id=tenant.id,
            unit_id=None,
            category="main",
            baseline_g_per_guest=400,
            protein_per_100g=10.0,
        )
        db.add(guideline)
        db.commit()
        return {"tenant_id": tenant.id, "user_id": user.id}
    finally:
        db.close()


def login(client, email):
    return client.post("/auth/login", json={"email": email, "password": "pw"})


def get_reco(client, category="main", guest_count=10):
    return client.get(f"/service/recommendation?category={category}&guest_count={guest_count}")


def test_baseline_fallback(client, setup_tenant):
    login(client, "portion_admin@example.com")
    rv = get_reco(client)
    assert rv.status_code == 200
    data = rv.get_json()
    # 400 baseline * 1.05 = 420
    assert data["recommended_g_per_guest"] == 420
    assert data["source"] == "baseline"
    assert data["total_gram"] == 420 * 10
    # protein: 10 per 100g => 0.1 * total_gram
    assert data["total_protein"] == pytest.approx(0.1 * 420 * 10, rel=1e-3)


def test_blend_few_points(client, setup_tenant):
    login(client, "portion_admin@example.com")
    db = get_session()
    try:
        t_id = setup_tenant["tenant_id"]
        base_date = date.today()
        values = [500, 450, 550]
        for i, v in enumerate(values):
            sm = ServiceMetric(
                tenant_id=t_id,
                unit_id=1,
                date=base_date - timedelta(days=i),
                meal="lunch",
                dish_id=None,
                category="main",
                guest_count=100,
                produced_qty_kg=60,
                served_qty_kg=50,
                leftover_qty_kg=10,
                served_g_per_guest=v,
            )
            db.add(sm)
        db.commit()
    finally:
        db.close()
    rv = get_reco(client)
    data = rv.get_json()
    assert data["source"] == "blended"
    assert data["sample_size"] == 3
    assert data["recommended_g_per_guest"] == 441  # see calculation above


def test_blend_many_points_trimmed(client, setup_tenant):
    login(client, "portion_admin@example.com")
    db = get_session()
    try:
        t_id = setup_tenant["tenant_id"]
        base_date = date.today()
        values = [300, 600, 500, 505, 495, 510, 490, 500, 500, 500]
        for i, v in enumerate(values):
            sm = ServiceMetric(
                tenant_id=t_id,
                unit_id=1,
                date=base_date - timedelta(days=i),
                meal="lunch",
                dish_id=None,
                category="main",
                guest_count=100,
                produced_qty_kg=60,
                served_qty_kg=50,
                leftover_qty_kg=10,
                served_g_per_guest=v,
            )
            db.add(sm)
        db.commit()
    finally:
        db.close()
    rv = get_reco(client)
    data = rv.get_json()
    # baseline 400, trimmed history mean ~500 => 0.3*400 + 0.7*500 = 470 -> *1.05 = 493.5 -> 494
    assert data["recommended_g_per_guest"] == 494
    assert data["sample_size"] == 10
    assert data["source"] == "blended"


def test_requires_params(client, setup_tenant):
    login(client, "portion_admin@example.com")
    rv = client.get("/service/recommendation?category=main")
    assert rv.status_code == 400
    rv = client.get("/service/recommendation?guest_count=10")
    assert rv.status_code == 400
