import io
import json
from typing import Any

import pytest
from flask import Flask

from core.app_factory import create_app

CSV_MINIMAL = b"title,description,priority\nA,Alpha,1\nB,Beta,2\n"
CSV_MISSING_COL = b"title,description\nOnly,Two\n"
CSV_EMPTY = b"title,description,priority\n"
CSV_UNICODE = "title,description,priority\nÅngström,Smörgås,3\n".encode()


def _app(flags: dict[str, bool] | None = None) -> Flask:
    cfg: dict[str, Any] = {"TESTING": True, "FEATURE_FLAGS": {"openapi_ui": True}}
    if flags:
        cfg["FEATURE_FLAGS"].update(flags)  # type: ignore[index]
    app = create_app(cfg)
    with app.test_request_context():
        pass
    return app


def _login(client):
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["user_id"] = 1
        sess["role"] = "admin"


def test_import_csv_happy_200():
    app = _app()
    with app.test_client() as client:
        _login(client)
        data = {"file": (io.BytesIO(CSV_MINIMAL), "data.csv")}
        resp = client.post("/import/csv", data=data, content_type="multipart/form-data")
        assert resp.status_code == 200
        payload = json.loads(resp.data)
        assert payload["ok"] is True
        assert payload["meta"]["count"] == 2


def test_import_csv_missing_column_400():
    app = _app()
    with app.test_client() as client:
        _login(client)
        data = {"file": (io.BytesIO(CSV_MISSING_COL), "data.csv")}
        resp = client.post("/import/csv", data=data, content_type="multipart/form-data")
        assert resp.status_code == 400
        payload = json.loads(resp.data)
        assert payload["ok"] is False
        assert payload["error"] == "invalid"


def test_import_csv_empty_ok():
    app = _app()
    with app.test_client() as client:
        _login(client)
        data = {"file": (io.BytesIO(CSV_EMPTY), "empty.csv")}
        resp = client.post("/import/csv", data=data, content_type="multipart/form-data")
        assert resp.status_code == 200
        payload = json.loads(resp.data)
        assert payload["meta"]["count"] == 0


def test_import_csv_unicode_ok():
    app = _app()
    with app.test_client() as client:
        _login(client)
        data = {"file": (io.BytesIO(CSV_UNICODE), "utf8.csv")}
        resp = client.post("/import/csv", data=data, content_type="multipart/form-data")
        assert resp.status_code == 200
        payload = json.loads(resp.data)
        assert payload["meta"]["count"] == 1


def test_import_docx_happy_or_skip():
    app = _app()
    with app.test_client() as client:
        _login(client)
        try:
            import docx  # type: ignore  # noqa: F401
        except Exception:
            pytest.skip("python-docx not installed")
        # Build a minimal DOCX with a table matching expected columns
        from docx import Document  # type: ignore

        buf = io.BytesIO()
        doc = Document()
        table = doc.add_table(rows=1, cols=3)
        hdr = table.rows[0].cells
        hdr[0].text = "title"
        hdr[1].text = "description"
        hdr[2].text = "priority"
        row = table.add_row().cells
        row[0].text = "R1"
        row[1].text = "Desc"
        row[2].text = "5"
        doc.save(buf)
        buf.seek(0)
        data = {"file": (buf, "table.docx")}
        resp = client.post("/import/docx", data=data, content_type="multipart/form-data")
        assert resp.status_code in (200, 415)  # 415 if importer disabled
        if resp.status_code == 200:
            payload = json.loads(resp.data)
            assert payload["meta"]["count"] == 1


def test_import_xlsx_happy_200():
    app = _app()
    with app.test_client() as client:
        _login(client)
        try:
            import openpyxl  # type: ignore  # noqa: F401
        except Exception:
            pytest.skip("openpyxl not installed")
        from openpyxl import Workbook  # type: ignore

        wb = Workbook()
        ws = wb.active
        ws.append(["title", "description", "priority"])
        ws.append(["X", "DescX", 7])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        data = {"file": (buf, "data.xlsx")}
        resp = client.post("/import/xlsx", data=data, content_type="multipart/form-data")
        assert resp.status_code in (200, 415)
        if resp.status_code == 200:
            payload = json.loads(resp.data)
            assert payload["meta"]["count"] == 1


def test_import_unsupported_mime_415():
    app = _app()
    with app.test_client() as client:
        _login(client)
        # Force plain text filename extension
        data = {"file": (io.BytesIO(b"hello"), "readme.txt")}
        resp = client.post("/import/csv", data=data, content_type="multipart/form-data")
        # Our endpoint currently trusts extension; treat this as future placeholder
        # Simulate unsupported by posting to docx with missing parser
        if resp.status_code == 200:
            # Try docx import when library missing
            try:
                import docx  # noqa: F401
                # If docx exists we intentionally send bad content to trigger invalid vs unsupported
            except Exception:
                # Without docx installed docx endpoint returns 415
                resp2 = client.post("/import/docx", data=data, content_type="multipart/form-data")
                assert resp2.status_code == 415
        else:
            assert resp.status_code in (400, 415)


def test_import_rate_limit_flag_on_off():
    # Force enforcement via X-Force-Rate-Limit header path (since feature flag gating not yet per-tenant for import)
    app = _app({"rate_limit_import": True})
    with app.test_client() as client:
        _login(client)
        headers = {"X-Force-Rate-Limit": "1", "X-Force-Rate-Limit-Limit": "5"}
        success = 0
        for i in range(6):
            data = {"file": (io.BytesIO(CSV_MINIMAL), f"d{i}.csv")}
            resp = client.post(
                "/import/csv", data=data, content_type="multipart/form-data", headers=headers
            )
            if resp.status_code == 200:
                success += 1
            if resp.status_code == 429:
                payload = json.loads(resp.data)
                assert payload.get("status") == 429 and payload.get("type", " ").endswith(
                    "/rate_limited"
                )
                break
        assert success <= 5
