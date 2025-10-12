import io
import json

from flask import Flask

from core.app_factory import create_app


def _app():
    return create_app({"TESTING": True})


def _login(client):
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["user_id"] = 10
        sess["role"] = "admin"


def test_menu_dry_run_true_sets_meta_flag(monkeypatch):
    app: Flask = _app()

    class DummyImporter:
        def parse(self, data, filename, mime):
            class Week:
                def __init__(self):
                    self.items = [
                        type(
                            "I",
                            (),
                            {
                                "day": "monday",
                                "meal": "lunch",
                                "variant_type": "alt1",
                                "dish_name": "Stew",
                            },
                        )()
                    ]

            return type("R", (), {"weeks": [Week()]})()

    import core.import_api as import_api_mod

    monkeypatch.setattr(import_api_mod, "_importer", DummyImporter())

    with app.test_client() as client:
        _login(client)
        data = {"file": (io.BytesIO(b"x"), "menu.xlsx")}
        resp = client.post("/import/menu?dry_run=1", data=data, content_type="multipart/form-data")
        assert resp.status_code == 200
        body = json.loads(resp.data)
        assert body["meta"]["dry_run"] is True
        assert body["meta"]["count"] == 1
        assert len(body["rows"]) == 1


def test_menu_unsupported_mime_415(monkeypatch):
    app: Flask = _app()
    import core.import_api as import_api_mod

    monkeypatch.setattr(import_api_mod, "_importer", None)
    with app.test_client() as client:
        _login(client)
        data = {"file": (io.BytesIO(b"x"), "menu.xlsx")}
        resp = client.post("/import/menu", data=data, content_type="multipart/form-data")
        assert resp.status_code in (415, 400)  # 415 when importer missing
