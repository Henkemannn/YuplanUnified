import pytest
from flask import Flask
from core.app_factory import create_app
from core.db import get_session, create_all
from core.models import Tenant, User, Note, Task
from werkzeug.security import generate_password_hash


@pytest.fixture()
def app():
    app = create_app({"TESTING": True, "SECRET_KEY": "test"})
    return app


@pytest.fixture()
def client(app: Flask):
    return app.test_client()


@pytest.fixture()
def seeded(client):
    # Ensure tables (if using clean SQLite file)
    try:
        create_all()
    except Exception:
        pass
    db = get_session()
    try:
        tenant = db.query(Tenant).first()
        if not tenant:
            tenant = Tenant(name='ExportT')
            db.add(tenant); db.commit(); db.refresh(tenant)
        # Clean possible previous runs
        db.query(Note).delete(); db.query(Task).delete(); db.query(User).filter(User.email.in_(['exp_admin@example.com','exp_cook@example.com'])).delete(); db.commit()
        admin = User(tenant_id=tenant.id, email='exp_admin@example.com', password_hash=generate_password_hash('pw'), role='admin', unit_id=None)
        cook = User(tenant_id=tenant.id, email='exp_cook@example.com', password_hash=generate_password_hash('pw'), role='cook', unit_id=None)
        db.add_all([admin, cook]); db.commit(); db.refresh(admin); db.refresh(cook)
        # Seed some data
        n1 = Note(tenant_id=tenant.id, user_id=admin.id, content='Public Note', private_flag=False)
        n2 = Note(tenant_id=tenant.id, user_id=admin.id, content='Privat Note', private_flag=True)
        db.add_all([n1, n2]); db.commit()
        t1 = Task(tenant_id=tenant.id, unit_id=None, task_type='prep', title='Hacka lök', done=False, private_flag=False)
        t2 = Task(tenant_id=tenant.id, unit_id=None, task_type='prep', title='Privat staging', done=True, private_flag=True, creator_user_id=admin.id)
        db.add_all([t1, t2]); db.commit()
        # Return primitive IDs to avoid DetachedInstance issues once session closed
        return {'tenant_id': tenant.id, 'admin_id': admin.id, 'cook_id': cook.id}
    finally:
        db.close()


def login(client, email):
    return client.post('/auth/login', json={'email': email, 'password': 'pw'})


def test_export_requires_admin_role(client, seeded):
    # login as cook (not admin)
    assert login(client, 'exp_cook@example.com').status_code == 200
    rv = client.get('/export/notes.csv')
    assert rv.status_code in (403, 401)


def test_export_notes_csv_basic(client, seeded):
    assert login(client, 'exp_admin@example.com').status_code == 200
    rv = client.get('/export/notes.csv')
    assert rv.status_code == 200
    assert rv.headers['Content-Type'].startswith('text/csv')
    body = rv.get_data(as_text=True)
    # header + both notes (private still included because admin)
    assert 'Public Note' in body and 'Privat Note' in body
    assert body.splitlines()[0].startswith('id,created_at')


def test_export_tasks_csv_separator_and_bom(client, seeded):
    assert login(client, 'exp_admin@example.com').status_code == 200
    rv = client.get('/export/tasks.csv?sep=;&bom=1')
    assert rv.status_code == 200
    text = rv.get_data(as_text=True)
    # BOM present
    assert text.startswith('\ufeff')
    first_line = text.splitlines()[0]
    assert ';' in first_line  # custom separator
    # Expect new timestamp columns in header
    assert 'created_at' in first_line and 'updated_at' in first_line


def test_export_streaming_large(client, seeded):
    # Add a few more rows to exercise generator (not a strict performance test)
    db = get_session()
    try:
        for i in range(5):
            db.add(Note(tenant_id=seeded['tenant_id'], user_id=seeded['admin_id'], content=f'Extra {i}', private_flag=False))
        db.commit()
    finally:
        db.close()
    assert login(client, 'exp_admin@example.com').status_code == 200
    rv = client.get('/export/notes.csv')
    assert rv.status_code == 200
    body = rv.get_data(as_text=True)
    # confirm at least 1 of the extra rows
    assert 'Extra 0' in body
