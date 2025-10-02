import json
from flask import Flask
from core.app_factory import create_app


def _app():
    return create_app({'TESTING': True})


def _login(client):
    with client.session_transaction() as sess:
        sess['tenant_id'] = 1
        sess['user_id'] = 1
        sess['role'] = 'admin'


def test_notes_alias_has_deprecation_headers():
    app: Flask = _app()
    with app.test_client() as client:
        _login(client)
        # create one note
        client.post('/notes/', json={'content': 'Hello'})
        resp = client.get('/notes/')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert 'notes' in data and 'items' in data
        assert resp.headers.get('Deprecation') == 'true'
        assert 'Sunset' in resp.headers
        link = resp.headers.get('Link')
        assert link and 'rel="deprecation"' in link


def test_tasks_alias_has_deprecation_headers():
    app: Flask = _app()
    with app.test_client() as client:
        _login(client)
        # create one task
        client.post('/tasks/', json={'title': 'X'})
        resp = client.get('/tasks/')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert 'tasks' in data and 'items' in data
        assert resp.headers.get('Deprecation') == 'true'
        assert 'Sunset' in resp.headers
        link = resp.headers.get('Link')
        assert link and 'rel="deprecation"' in link
