from core.app_factory import create_app
from core.db import get_session
from core.models import Tenant, User
from werkzeug.security import generate_password_hash
import uuid


def _bootstrap(db):
    t = Tenant(name='MenuT_' + uuid.uuid4().hex[:6])
    db.add(t); db.flush()
    u = User(tenant_id=t.id, email=f"cook_{uuid.uuid4().hex[:6]}@ex.com", password_hash=generate_password_hash('pw'), role='cook', unit_id=None)
    db.add(u); db.commit()
    return t, u

def _login(client, email):
    r = client.post('/auth/login', json={'email': email, 'password': 'pw'})
    assert r.status_code == 200


def test_menu_variant_set_and_week_view():
    app = create_app({'TESTING': True, 'SECRET_KEY': 'x'})
    client = app.test_client()
    db = get_session()
    t, u = _bootstrap(db)
    user_email = u.email
    db.close()

    _login(client, user_email)

    payload = {
        'week': 40,
        'year': 2025,
        'day': 'Mon',
        'meal': 'Lunch',
        'variant_type': 'alt1',
        'dish_name': 'Pasta Bolognese'
    }
    r = client.post('/menu/variant/set', json=payload)
    assert r.status_code == 200
    mv_id = r.get_json()['menu_variant_id']
    assert mv_id is not None

    # Set second variant referencing same dish by name again (idempotent dish creation)
    payload2 = {
        'week': 40,
        'year': 2025,
        'day': 'Mon',
        'meal': 'Lunch',
        'variant_type': 'dessert',
        'dish_name': 'Pasta Bolognese'
    }
    r2 = client.post('/menu/variant/set', json=payload2)
    assert r2.status_code == 200

    # Retrieve week
    week_resp = client.get('/menu/week', query_string={'week': 40, 'year': 2025})
    assert week_resp.status_code == 200
    data = week_resp.get_json()
    assert data['ok'] is True
    days = data['menu']['days']
    assert 'Mon' in days
    lunch = days['Mon']['Lunch']
    assert lunch['alt1']['dish_name'] == 'Pasta Bolognese'
    assert lunch['dessert']['dish_name'] == 'Pasta Bolognese'

    # Update alt1 variant to a different dish name (new dish)
    r3 = client.post('/menu/variant/set', json={**payload, 'dish_name': 'Fish Pie'})
    assert r3.status_code == 200
    week_resp2 = client.get('/menu/week', query_string={'week': 40, 'year': 2025})
    lunch2 = week_resp2.get_json()['menu']['days']['Mon']['Lunch']
    assert lunch2['alt1']['dish_name'] == 'Fish Pie'
    # Dessert unchanged
    assert lunch2['dessert']['dish_name'] == 'Pasta Bolognese'