from __future__ import annotations

import io
import re
import uuid
import zipfile
import xml.etree.ElementTree as ET

import pytest
from werkzeug.datastructures import FileStorage

from core.importers.docx_table_importer import parse_docx
from core.importers.xlsx_importer import parse_xlsx
from core.upload_limits import (
    InvalidUpload,
    UploadTooLarge,
    bounded_read,
    validate_csv_bytes,
    validate_zip_payload,
)


@pytest.fixture(autouse=True)
def restore_upload_policy_overrides(app_session):
    previous = app_session.config.get("UPLOAD_POLICY_OVERRIDES")
    previous_strict = app_session.config.get("YUPLAN_STRICT_CSRF")
    previous_strict_tests = app_session.config.get("STRICT_CSRF_IN_TESTS")
    yield
    if previous is None:
        app_session.config.pop("UPLOAD_POLICY_OVERRIDES", None)
    else:
        app_session.config["UPLOAD_POLICY_OVERRIDES"] = previous
    app_session.config["YUPLAN_STRICT_CSRF"] = previous_strict
    app_session.config["STRICT_CSRF_IN_TESTS"] = previous_strict_tests


def _set_limits(app, **values):
    app.config["UPLOAD_POLICY_OVERRIDES"] = values


def _rewrite_xlsx_dimension(payload: bytes, reference: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(payload)) as source, zipfile.ZipFile(
        output, "w"
    ) as target:
        for item in source.infolist():
            content = source.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                content = re.sub(
                    rb'<dimension ref="[^"]+"',
                    f'<dimension ref="{reference}"'.encode("ascii"),
                    content,
                    count=1,
                )
            target.writestr(item, content)
    return output.getvalue()


def _xlsx_with_dish() -> bytes:
    from openpyxl import Workbook

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(["dish", "description"])
    worksheet.append(["Fish", "Fresh fish"])
    stream = io.BytesIO()
    workbook.save(stream)
    workbook.close()
    return stream.getvalue()


def _xlsx_with_worksheet_order(count: int) -> bytes:
    from openpyxl import Workbook

    workbook = Workbook()
    first = workbook.active
    first.title = "LogicalFirst"
    for index, worksheet in enumerate([first] + [workbook.create_sheet() for _ in range(count - 1)], 1):
        worksheet.append(
            [f"dish{index}", f"description{index}"]
            + [f"column{index}_{column}" for column in range(3, index + 3)]
        )
        for row in range(1, index + 1):
            worksheet.append(
                [f"Meal {index}-{row}", f"Description {index}-{row}"]
                + [f"Value {index}-{row}-{column}" for column in range(3, index + 3)]
            )
    stream = io.BytesIO()
    workbook.save(stream)
    workbook.close()
    return stream.getvalue()


def _rebind_worksheet_targets(payload: bytes, targets: list[str]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(payload)) as source, zipfile.ZipFile(
        output, "w"
    ) as target:
        worksheet_index = 0
        for item in source.infolist():
            content = source.read(item.filename)
            if item.filename == "xl/_rels/workbook.xml.rels":
                root = ET.fromstring(content)
                for relationship in root:
                    if relationship.attrib.get("Type", "").endswith("/worksheet"):
                        relationship.set(
                            "Target", f"worksheets/{targets[worksheet_index]}"
                        )
                        worksheet_index += 1
                content = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            target.writestr(item, content)
    return output.getvalue()


def _remove_worksheet_relationship(payload: bytes) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(payload)) as source, zipfile.ZipFile(
        output, "w"
    ) as target:
        for item in source.infolist():
            content = source.read(item.filename)
            if item.filename == "xl/_rels/workbook.xml.rels":
                content = content.replace(b'Id="rId1"', b'Id="rId_missing"')
            target.writestr(item, content)
    return output.getvalue()


def _empty_xlsx() -> bytes:
    from openpyxl import Workbook

    workbook = Workbook()
    stream = io.BytesIO()
    workbook.save(stream)
    workbook.close()
    return _rewrite_xlsx_dimension(stream.getvalue(), "A1:XFD1048576")


def _real_admin_client(app):
    from werkzeug.security import generate_password_hash

    from core.admin_repo import SitesRepo
    from core.db import get_session
    from core.models import Tenant, User
    from sqlalchemy import text

    db = get_session()
    tenant = Tenant(name="F13_" + uuid.uuid4().hex[:8])
    db.add(tenant)
    db.flush()
    user = User(
        tenant_id=tenant.id,
        email=f"f13_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=generate_password_hash("F13-password"),
        role="admin",
        unit_id=None,
    )
    email = str(user.email)
    db.add(user)
    db.commit()
    user_id = int(user.id)
    tenant_id = int(tenant.id)
    site, _ = SitesRepo().create_site("F13 site", tenant_id=tenant_id)
    db.execute(
        text(
            "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
            "user_id INTEGER NOT NULL, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL)"
        )
    )
    db.execute(
        text("DELETE FROM kitchen_user_sites WHERE user_id=:uid"),
        {"uid": user_id},
    )
    db.execute(
        text(
            "INSERT INTO kitchen_user_sites (user_id, tenant_id, site_id) "
            "VALUES (:uid, :tid, :sid)"
        ),
        {"uid": user_id, "tid": tenant_id, "sid": str(site["id"])},
    )
    db.commit()
    site_id = str(site["id"])
    db.close()

    client = app.test_client()
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "F13-password"},
    )
    assert login.status_code == 200
    with client.session_transaction() as session:
        assert session.get("tenant_id") == tenant_id
        assert session.get("site_id") == site_id
    return client


def test_bounded_read_rejects_before_parser_input_is_complete() -> None:
    class InstrumentedStream:
        def __init__(self) -> None:
            self.calls = 0

        def read(self, size: int) -> bytes:
            self.calls += 1
            return b"x" * size

    stream = InstrumentedStream()
    with pytest.raises(UploadTooLarge):
        bounded_read(stream, 8)
    assert stream.calls == 1


def test_bounded_read_accepts_exact_limit() -> None:
    assert bounded_read(io.BytesIO(b"12345678"), 8) == b"12345678"


def test_bounded_read_accepts_short_stream_reads() -> None:
    class ShortReadStream:
        def __init__(self) -> None:
            self.parts = [b"123", b"45", b""]

        def read(self, size: int) -> bytes:
            del size
            return self.parts.pop(0)

    assert bounded_read(ShortReadStream(), 5) == b"12345"


def test_import_request_limit_returns_413_before_form_parse(app_session, client_admin):
    _set_limits(app_session, request_bytes=256)
    response = client_admin.post(
        "/import/csv",
        data={"file": (io.BytesIO(b"title\nDish\n"), "menu.csv")},
        content_type="multipart/form-data",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert response.status_code == 413
    assert response.get_json()["error"] == "request_too_large"


def test_upload_limit_hook_precedes_security_and_strict_csrf(app_session, client_admin):
    app_session.config.update(
        {"YUPLAN_STRICT_CSRF": True, "STRICT_CSRF_IN_TESTS": True}
    )
    _set_limits(app_session, request_bytes=256)
    names = [
        getattr(fn, "__name__", "")
        for fn in app_session.before_request_funcs.get(None, [])
    ]
    assert names.index("_apply_upload_request_limits") < names.index(
        "_security_before_request"
    )
    response = client_admin.post(
        "/ui/admin/menu-import/upload",
        data={"menu_file": (io.BytesIO(b"x" * 512), "menu.csv")},
        content_type="multipart/form-data",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert response.status_code == 413
    body = response.get_data(as_text=True)
    assert "Uppladdningen är för stor" in body
    assert "Tillbaka till menyimporten" in body
    assert "menu-import" in body


def test_request_limit_rejects_terminated_stream_without_content_length(
    app_session, client_admin
) -> None:
    from werkzeug.test import Client, EnvironBuilder
    from werkzeug.wrappers import Response as WerkzeugResponse

    _set_limits(app_session, request_bytes=8)
    builder = EnvironBuilder(
        method="POST",
        path="/import/csv",
        input_stream=io.BytesIO(b"0123456789"),
        content_type="application/octet-stream",
        content_length=None,
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    environ = builder.get_environ()
    environ.pop("CONTENT_LENGTH", None)
    environ["wsgi.input_terminated"] = True
    response = Client(app_session, WerkzeugResponse).open(environ)
    assert response.status_code == 413


def test_multipart_part_limit_returns_413(app_session, client_admin):
    _set_limits(app_session, request_bytes=1024 * 1024, multipart_parts=10)
    data = {"file": (io.BytesIO(b"title\nDish\n"), "menu.csv")}
    data.update({f"extra_{index}": str(index) for index in range(10)})
    response = client_admin.post(
        "/import/csv",
        data=data,
        content_type="multipart/form-data",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert response.status_code == 413


def test_import_file_limit_rejects_before_csv_parser(
    app_session, client_admin, monkeypatch
) -> None:
    _set_limits(app_session, csv_bytes=4)
    import core.import_api as import_api

    called = False

    def parser(_: str):
        nonlocal called
        called = True
        raise AssertionError("parser must not run")

    monkeypatch.setattr(import_api, "parse_csv", parser)
    response = client_admin.post(
        "/import/csv",
        data={"file": (io.BytesIO(b"title\n"), "menu.csv")},
        content_type="multipart/form-data",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert response.status_code == 413
    assert called is False


def test_csv_limits_reject_rows_columns_and_cells(app_session) -> None:
    with app_session.app_context():
        _set_limits(app_session, rows_total=1, columns_per_row=2, cells_total=2)
        with pytest.raises(UploadTooLarge):
            validate_csv_bytes(b"a,b\n1,2\n3,4\n")
        with pytest.raises(UploadTooLarge):
            validate_csv_bytes(b"a,b,c\n1,2,3\n")


def test_zip_limits_check_actual_expansion(app_session) -> None:
    with app_session.app_context():
        _set_limits(app_session, zip_total_bytes=4, zip_entry_bytes=4)
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("document.xml", b"12345")
        with pytest.raises(UploadTooLarge):
            validate_zip_payload(stream.getvalue())


def test_zip_declared_entry_size_is_checked_separately(app_session) -> None:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_STORED) as archive:
        archive.writestr("document.xml", b"12345")
    with app_session.app_context():
        _set_limits(app_session, zip_total_bytes=100, zip_entry_bytes=4)
        with pytest.raises(UploadTooLarge):
            validate_zip_payload(stream.getvalue())


def test_zip_actual_read_size_is_checked_separately(app_session, monkeypatch) -> None:
    import core.upload_limits as upload_limits

    class FakeMember:
        def __init__(self) -> None:
            self.reads = [b"12345", b""]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size: int) -> bytes:
            del size
            return self.reads.pop(0)

    class FakeInfo:
        file_size = 1

        def is_dir(self) -> bool:
            return False

    class FakeArchive:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def infolist(self):
            return [FakeInfo()]

        def open(self, entry):
            del entry
            return FakeMember()

        def close(self):
            return None

    monkeypatch.setattr(upload_limits.zipfile, "ZipFile", lambda *_args: FakeArchive())
    with app_session.app_context():
        _set_limits(app_session, zip_total_bytes=4, zip_entry_bytes=100)
        with pytest.raises(UploadTooLarge):
            validate_zip_payload(b"synthetic")


def test_zip_entry_count_limit(app_session) -> None:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("one.xml", b"1")
        archive.writestr("two.xml", b"2")
    with app_session.app_context():
        _set_limits(app_session, zip_entries=1)
        with pytest.raises(UploadTooLarge):
            validate_zip_payload(stream.getvalue())


def test_zip_entry_limit_is_separate_from_total_limit(app_session) -> None:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_STORED) as archive:
        archive.writestr("one.xml", b"12345")
    with app_session.app_context():
        _set_limits(app_session, zip_total_bytes=100, zip_entry_bytes=4)
        with pytest.raises(UploadTooLarge):
            validate_zip_payload(stream.getvalue())


def test_xlsx_limits_apply_across_rows_and_close_workbook(app_session) -> None:
    from openpyxl import Workbook

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(["title", "description"])
    worksheet.append(["Dish", "Description"])
    stream = io.BytesIO()
    workbook.save(stream)
    workbook.close()

    with app_session.app_context():
        _set_limits(app_session, rows_total=1)
        with pytest.raises(UploadTooLarge):
            parse_xlsx(stream.getvalue())


def test_xlsx_rejects_misleading_wide_dimension_before_row_materialization(
    app_session,
) -> None:
    from openpyxl import Workbook

    workbook = Workbook()
    workbook.active.cell(row=1, column=20).value = "wide"
    stream = io.BytesIO()
    workbook.save(stream)
    workbook.close()

    with app_session.app_context():
        _set_limits(app_session, columns_per_row=4)
        with pytest.raises(UploadTooLarge):
            parse_xlsx(stream.getvalue())


def test_xlsx_uses_actual_dimensions_when_declaration_is_too_small_or_large(
    app_session,
) -> None:
    payload = _xlsx_with_dish()
    too_small = _rewrite_xlsx_dimension(payload, "A1:A1")
    too_large = _rewrite_xlsx_dimension(payload, "A1:XFD1048576")

    with app_session.app_context():
        result_small = parse_xlsx(too_small)
        result_large = parse_xlsx(too_large)
    assert result_small.rows[0]["dish"] == "Fish"
    assert result_large.rows[0]["dish"] == "Fish"

    from core.builder.file_import import parse_builder_import_file

    with app_session.app_context():
        for data in (too_small, too_large):
            preview = parse_builder_import_file(
                FileStorage(stream=io.BytesIO(data), filename="menu.xlsx")
            )
            assert "Fish" in preview.lines


def test_xlsx_worksheet_relationships_bind_dimensions_in_workbook_order(
    app_session,
) -> None:
    payload = _xlsx_with_worksheet_order(2)
    rebound = _rebind_worksheet_targets(payload, ["sheet2.xml", "sheet1.xml"])

    with app_session.app_context():
        result = parse_xlsx(rebound)
    assert list(result.headers) == [
        "dish2",
        "description2",
        "column2_3",
        "column2_4",
    ]
    assert [row["dish2"] for row in result.rows] == ["Meal 2-1", "Meal 2-2"]
    assert [row["description2"] for row in result.rows] == [
        "Description 2-1",
        "Description 2-2",
    ]

    from core.builder.file_import import parse_builder_import_file

    with app_session.app_context():
        preview = parse_builder_import_file(
            FileStorage(stream=io.BytesIO(rebound), filename="menu.xlsx")
        )
    assert preview.lines == ["dish2", "Meal 2-1", "Meal 2-2"]


def test_xlsx_sheet10_is_not_confused_with_sheet2(app_session) -> None:
    payload = _xlsx_with_worksheet_order(11)
    rebound = _rebind_worksheet_targets(
        payload, [f"sheet{index}.xml" for index in range(11, 0, -1)]
    )

    with app_session.app_context():
        result = parse_xlsx(rebound)
    assert len(result.headers) == 13
    assert len(result.rows) == 11
    assert result.rows[-1]["dish11"] == "Meal 11-11"
    assert result.rows[-1]["description11"] == "Description 11-11"

    from core.builder.file_import import parse_builder_import_file

    with app_session.app_context():
        preview = parse_builder_import_file(
            FileStorage(stream=io.BytesIO(rebound), filename="menu.xlsx")
        )
    assert preview.lines == ["dish11"] + [
        f"Meal 11-{row}" for row in range(1, 12)
    ]


def test_xlsx_missing_worksheet_relationship_is_rejected(app_session) -> None:
    payload = _remove_worksheet_relationship(_xlsx_with_dish())
    with app_session.app_context():
        with pytest.raises(InvalidUpload):
            parse_xlsx(payload)


def test_xlsx_inconsistent_worksheet_relationship_is_rejected(app_session) -> None:
    payload = _xlsx_with_worksheet_order(2)
    rebound = _rebind_worksheet_targets(payload, ["sheet1.xml", "sheet1.xml"])
    with app_session.app_context():
        with pytest.raises(InvalidUpload):
            parse_xlsx(rebound)


def test_empty_xlsx_with_misleading_dimension_does_not_materialize_cells(
    app_session, monkeypatch
) -> None:
    import openpyxl.worksheet._read_only as read_only

    def fail_if_materialized(*args, **kwargs):
        raise AssertionError("empty worksheet attempted cell materialization")

    monkeypatch.setattr(read_only.ReadOnlyWorksheet, "iter_rows", fail_if_materialized)
    payload = _empty_xlsx()
    _set_limits(app_session, rows_total=1, cells_total=1)

    with app_session.app_context():
        assert parse_xlsx(payload).rows == []
        from core.builder.file_import import parse_builder_import_file

        with pytest.raises(ValueError, match="no importable rows"):
            parse_builder_import_file(
                FileStorage(stream=io.BytesIO(payload), filename="empty.xlsx")
            )


def test_xlsx_cell_and_text_limits_are_aggregated(app_session) -> None:
    from openpyxl import Workbook

    workbook = Workbook()
    workbook.active.append(["a", "b"])
    workbook.active.append(["c", "d"])
    stream = io.BytesIO()
    workbook.save(stream)
    workbook.close()

    with app_session.app_context():
        _set_limits(app_session, cells_total=3)
        with pytest.raises(UploadTooLarge):
            parse_xlsx(stream.getvalue())

    workbook = Workbook()
    workbook.active.append(["x" * 20])
    stream = io.BytesIO()
    workbook.save(stream)
    workbook.close()
    with app_session.app_context():
        _set_limits(app_session, text_bytes=8)
        with pytest.raises(UploadTooLarge):
            parse_xlsx(stream.getvalue())


def test_docx_limits_reject_large_cell_before_import(app_session) -> None:
    from docx import Document

    document = Document()
    table = document.add_table(rows=1, cols=1)
    table.cell(0, 0).text = "x" * 20
    stream = io.BytesIO()
    document.save(stream)

    with app_session.app_context():
        _set_limits(app_session, cell_text_bytes=8)
        with pytest.raises(UploadTooLarge):
            parse_docx(stream.getvalue())


def test_docx_counts_free_standing_paragraphs(app_session) -> None:
    from docx import Document

    document = Document()
    document.add_paragraph("one")
    document.add_paragraph("two")
    stream = io.BytesIO()
    document.save(stream)

    with app_session.app_context():
        _set_limits(app_session, rows_total=1)
        with pytest.raises(UploadTooLarge):
            parse_docx(stream.getvalue())


def test_docx_merged_cells_count_logical_positions(app_session) -> None:
    from docx import Document

    document = Document()
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).merge(table.cell(0, 1)).text = "merged"
    stream = io.BytesIO()
    document.save(stream)

    with app_session.app_context():
        _set_limits(app_session, cells_total=1)
        with pytest.raises(UploadTooLarge):
            parse_docx(stream.getvalue())
        _set_limits(app_session, cells_total=2)
        parse_docx(stream.getvalue())


def test_docx_table_limit_rejects_before_import(app_session) -> None:
    from docx import Document

    document = Document()
    document.add_table(rows=1, cols=1)
    stream = io.BytesIO()
    document.save(stream)

    with app_session.app_context():
        _set_limits(app_session, docx_tables=0)
        with pytest.raises(UploadTooLarge):
            parse_docx(stream.getvalue())


def test_xlsx_sheet_limit_rejects_before_import(app_session) -> None:
    from openpyxl import Workbook

    workbook = Workbook()
    workbook.create_sheet("Second")
    stream = io.BytesIO()
    workbook.save(stream)
    workbook.close()

    with app_session.app_context():
        _set_limits(app_session, xlsx_sheets=1)
        with pytest.raises(UploadTooLarge):
            parse_xlsx(stream.getvalue())


def test_builder_txt_limit_is_applied_before_preview_parser(app_session) -> None:
    from core.builder.file_import import parse_builder_import_file

    with app_session.app_context():
        _set_limits(app_session, txt_bytes=4)
        with pytest.raises(UploadTooLarge):
            parse_builder_import_file(
                FileStorage(stream=io.BytesIO(b"Dish\n"), filename="menu.txt")
            )


def test_admin_oversized_csv_is_rejected_before_persistence(
    app_session, client_admin, monkeypatch
) -> None:
    from core.menu_import_service import MenuImportService
    from tests.admin.test_admin_f01a_scope import bind_current_test_site

    _set_limits(app_session, csv_bytes=4)
    bind_current_test_site(app_session, client_admin)
    monkeypatch.setattr(
        MenuImportService,
        "apply",
        lambda *args, **kwargs: pytest.fail("rejected upload must not mutate data"),
    )
    response = client_admin.post(
        "/ui/admin/menu-import/upload",
        data={"menu_file": (io.BytesIO(b"Year,Week\n"), "menu.csv")},
        content_type="multipart/form-data",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert response.status_code == 413
    assert "menu-import" in response.headers["Location"]
    assert "Filen överskrider tillåten storlek." in response.get_data(as_text=True)


def test_admin_oversized_docx_returns_413_before_persistence(
    app_session, client_admin, monkeypatch
) -> None:
    from core.menu_import_service import MenuImportService
    from tests.admin.test_admin_f01a_scope import bind_current_test_site

    _set_limits(app_session, document_bytes=4)
    bind_current_test_site(app_session, client_admin)
    monkeypatch.setattr(
        MenuImportService,
        "apply",
        lambda *args, **kwargs: pytest.fail("rejected upload must not mutate data"),
    )
    response = client_admin.post(
        "/ui/admin/menu-import/upload",
        data={"menu_file": (io.BytesIO(b"12345"), "menu.docx")},
        content_type="multipart/form-data",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert response.status_code == 413
    assert "menu-import" in response.headers["Location"]
    assert "Filen överskrider tillåten storlek." in response.get_data(as_text=True)


def test_real_admin_login_and_csrf_receive_safe_413_without_mutation(
    app_session, monkeypatch
) -> None:
    from core.menu_import_service import MenuImportService

    app_session.config.update(
        {"YUPLAN_STRICT_CSRF": True, "STRICT_CSRF_IN_TESTS": True}
    )
    _set_limits(app_session, csv_bytes=4)
    client = _real_admin_client(app_session)
    client.get("/health")
    with client.session_transaction() as session:
        csrf_token = session.get("CSRF_TOKEN")
    assert csrf_token
    monkeypatch.setattr(
        MenuImportService,
        "apply",
        lambda *args, **kwargs: pytest.fail("rejected upload must not mutate data"),
    )
    response = client.post(
        "/ui/admin/menu-import/upload",
        data={"menu_file": (io.BytesIO(b"Year,Week\n"), "menu.csv")},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 413
    body = response.get_data(as_text=True)
    assert "Filen överskrider tillåten storlek." in body
    assert "Traceback" not in body


def test_builder_preview_lines_enforces_text_limit(app_session, client_admin) -> None:
    _set_limits(app_session, text_bytes=8)
    response = client_admin.post(
        "/api/builder/import/preview-lines",
        json={"lines": ["123456789"]},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert response.status_code == 413
    assert response.get_json()["error"] == "too_large"


def test_malformed_documents_return_controlled_400(app_session, client_admin) -> None:
    for filename, endpoint in (
        ("bad.docx", "/import/docx"),
        ("bad.xlsx", "/import/xlsx"),
    ):
        response = client_admin.post(
            endpoint,
            data={"file": (io.BytesIO(b"not-a-zip"), filename)},
            content_type="multipart/form-data",
            headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
        )
        assert response.status_code == 400
        body = response.get_data(as_text=True)
        assert "BadZipFile" not in body
        assert "Traceback" not in body


def test_structurally_invalid_office_zip_returns_controlled_400(
    app_session, client_admin
) -> None:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("unrelated.xml", b"<not-an-office-document/>")
    for filename, endpoint in (
        ("bad.docx", "/import/docx"),
        ("bad.xlsx", "/import/xlsx"),
    ):
        response = client_admin.post(
            endpoint,
            data={"file": (io.BytesIO(stream.getvalue()), filename)},
            content_type="multipart/form-data",
            headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
        )
        assert response.status_code == 400
        body = response.get_data(as_text=True)
        assert "KeyError" not in body
        assert "Traceback" not in body
