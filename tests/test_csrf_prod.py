from html.parser import HTMLParser
import secrets

from sqlalchemy import text

from core import create_app
from core.db import create_all


class _SettingsFormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.fields = {}
        self._in_settings_form = False
        self._textarea_name = None
        self._textarea_value = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self._in_settings_form = attrs.get("action", "").endswith("/settings")
        elif self._in_settings_form and tag == "input" and attrs.get("name"):
            self.fields.setdefault(attrs["name"], []).append(attrs.get("value", ""))
        elif self._in_settings_form and tag == "textarea" and attrs.get("name"):
            self._textarea_name = attrs["name"]
            self._textarea_value = []

    def handle_data(self, data):
        if self._textarea_name:
            self._textarea_value.append(data)

    def handle_endtag(self, tag):
        if tag == "textarea" and self._textarea_name:
            self.fields.setdefault(self._textarea_name, []).append(
                "".join(self._textarea_value)
            )
            self._textarea_name = None
        elif tag == "form":
            self._in_settings_form = False


class _CsrfMarkupParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta_tokens = []
        self.form_tokens = []
        self._in_department_form = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and attrs.get("name") == "csrf-token":
            self.meta_tokens.append(attrs.get("content", ""))
        elif tag == "form":
            self._in_department_form = attrs.get("action", "").startswith(
                "/ui/admin/departments/"
            ) or "data-department-delete-form" in attrs
        elif (
            self._in_department_form
            and tag == "input"
            and attrs.get("name") == "csrf_token"
        ):
            self.form_tokens.append(attrs.get("value", ""))

    def handle_endtag(self, tag):
        if tag == "form":
            self._in_department_form = False


def _make_app(tmp_path, monkeypatch, *, testing=False, strict_csrf=False):
    # Force production-like CSRF (TESTING False) but keep other defaults.
    # We explicitly disable TESTING to exercise production policy.
    database_url = f"sqlite:///{(tmp_path / 'csrf_main.db').as_posix()}"
    builder_db_path = tmp_path / "csrf_builder.db"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("BUILDER_DB_PATH", str(builder_db_path))
    app = create_app(
        {
            "TESTING": testing,
            "STRICT_CSRF_IN_TESTS": strict_csrf,
            "SECRET_KEY": "csrf-secret",
            "ENABLE_CSRF": True,
            "AUTH_RATE_LIMIT_HMAC_SECRET": "csrf-rate-limit-test-secret",
            "database_url": database_url,
            "BUILDER_DB_PATH": str(builder_db_path),
        }
    )
    with app.app_context():
        create_all()
    return app


def test_post_without_token_forbidden(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()
    # Provide Origin to ensure CSRF evaluated before route handler might reject
    r = client.post("/features/set", json={"name": "csrf_test", "enabled": True}, headers={"Origin": "http://localhost"})
    if r.status_code == 401:
        # Auth layer fired first; acceptable, skip strict assertion
        return
    assert r.status_code == 403, r.get_data(as_text=True)
    assert r.mimetype == "application/problem+json"
    body = r.get_json()
    assert body.get("detail") in {"csrf_missing", "origin_mismatch"}


def test_double_submit_token_allows_protected_post(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch, strict_csrf=True)
    client = app.test_client()
    token = secrets.token_hex(8)
    cookie_name = app.config.get("CSRF_COOKIE_NAME", "csrf_token")
    header_name = app.config.get("CSRF_HEADER_NAME", "X-CSRF-Token")
    client.set_cookie(cookie_name, token)

    r = client.post(
        "/auth/reset",
        json={"token": "invalid", "password": "NotARealPassword123!"},
        headers={header_name: token},
    )
    assert r.status_code == 400
    body = r.get_data(as_text=True)
    assert "invalid_csrf" not in body
    assert "csrf_missing" not in body


def test_invalid_double_submit_token_is_forbidden(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch, strict_csrf=True)
    client = app.test_client()
    client.set_cookie("csrf_token", secrets.token_hex(8))

    response = client.post(
        "/auth/reset",
        json={"token": "invalid", "password": "NotARealPassword123!"},
        headers={"X-CSRF-Token": secrets.token_hex(8)},
    )

    assert response.status_code == 403
    assert response.get_json()["detail"] == "invalid_csrf"


def test_missing_double_submit_token_is_forbidden(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch, strict_csrf=True)
    client = app.test_client()

    response = client.post(
        "/auth/reset",
        json={"token": "invalid", "password": "NotARealPassword123!"},
    )

    assert response.status_code == 403
    assert response.get_json()["detail"] == "invalid_csrf"


def test_origin_mismatch_blocked(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()
    # Supply an Origin that is not the host
    r = client.post("/features/set", json={"name": "csrf_origin", "enabled": True}, headers={"Origin": "http://evil.example"})
    if r.status_code == 401:
        return  # auth took precedence
    assert r.status_code == 403
    body = r.get_json()
    assert body.get("detail") == "origin_mismatch"


def test_safe_methods_ok_without_token(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()
    for method in ("GET", "HEAD", "OPTIONS"):
        resp = client.open(path="/features", method=method)
        # Unauthenticated may yield 401; CSRF should not interfere with safe methods.
        assert resp.status_code in {200, 401, 404}


def test_prod_exempt_paths_require_token_for_write(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()
    # A non-exempt path must be blocked without a token.
    r_block = client.post("/features/set", json={"name": "csrf_write", "enabled": True})
    assert r_block.status_code in (401, 403)
    if r_block.status_code == 403:
        assert r_block.get_json()["detail"] == "invalid_csrf"

    # /auth/login is CSRF-exempt in production, but rate limiting remains active.
    r_auth = client.post("/auth/login", json={"email": "a@b", "password": "pw"})
    assert r_auth.status_code == 401
    assert "csrf_" not in r_auth.get_data(as_text=True)


def test_department_settings_requires_strict_csrf_outside_testing(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("YUPLAN_STRICT_CSRF", "1")
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()
    path = "/ui/admin/departments/11111111-1111-4111-8111-111111111111/settings"

    missing = client.post(path, data={})
    assert missing.status_code == 403
    assert missing.get_json()["detail"] == "csrf_missing"

    client.get(path)
    with client.session_transaction() as browser_session:
        token = browser_session.get("CSRF_TOKEN")
    assert token

    invalid = client.post(
        path, data={}, headers={"X-CSRF-Token": "invalid-department-token"}
    )
    assert invalid.status_code == 403
    assert invalid.get_json()["detail"] == "csrf_invalid"

    valid = client.post(
        path, data={}, headers={"X-CSRF-Token": token}
    )
    assert valid.status_code in (302, 401, 403)
    if valid.status_code == 403:
        assert valid.get_json()["detail"] not in {
            "csrf_missing",
            "csrf_invalid",
        }


def test_department_settings_browser_form_submits_rendered_csrf_token(
    tmp_path, monkeypatch
):
    from core.admin_repo import DepartmentsRepo, DietTypesRepo, SitesRepo
    from core.db import get_session
    from core.models import Tenant
    from tests._auth_site_helpers import login_bound_user

    monkeypatch.setenv("YUPLAN_STRICT_CSRF", "1")
    app = _make_app(tmp_path, monkeypatch)
    assert app.config["TESTING"] is False
    client = app.test_client()

    with app.app_context():
        db = get_session()
        try:
            if db.query(Tenant).filter(Tenant.id == 1).first() is None:
                db.add(Tenant(id=1, name="Settings CSRF Tenant"))
                db.commit()
        finally:
            db.close()

        site, _ = SitesRepo().create_site(
            name="Settings CSRF Site",
            tenant_id=1,
        )
        department, _ = DepartmentsRepo().create_department(
            site_id=site["id"],
            name="Settings CSRF Department",
            resident_count_mode="fixed",
            resident_count_fixed=10,
            notes="Before save",
        )
        diet_id = DietTypesRepo().create(
            site_id=site["id"],
            tenant_id=1,
            name="Settings CSRF Diet",
            semantics="atomic",
        )
        departments_repo = DepartmentsRepo()
        departments_repo.upsert_department_diet_defaults(
            department["id"],
            departments_repo.get_version(department["id"]) or 0,
            [{"diet_type_id": str(diet_id), "default_count": 2}],
        )

    login_bound_user(client, site_id=site["id"])
    settings_path = f"/ui/admin/departments/{department['id']}/settings"
    response = client.get(settings_path)
    assert response.status_code == 200

    parser = _SettingsFormParser()
    parser.feed(response.get_data(as_text=True))
    assert parser.fields["diet_type_id[]"] == [str(diet_id)]
    assert parser.fields["planned_count[]"] == ["2"]
    with client.session_transaction() as browser_session:
        expected_token = browser_session["CSRF_TOKEN"]
    assert parser.fields["csrf_token"] == [expected_token]

    for path in (
        "/ui/admin/departments",
        "/ui/admin/departments/new",
        f"/ui/admin/departments/{department['id']}/edit",
    ):
        page = client.get(path)
        assert page.status_code == 200, page.get_data(as_text=True)
        markup_parser = _CsrfMarkupParser()
        markup_parser.feed(page.get_data(as_text=True))
        assert markup_parser.meta_tokens == [expected_token]
        assert markup_parser.form_tokens
        assert all(token == expected_token for token in markup_parser.form_tokens)

    form_data = {
        key: values[0] if len(values) == 1 else values
        for key, values in parser.fields.items()
    }
    form_data["residents_base_count"] = "15"
    form_data["notes"] = "Saved from rendered browser form"
    form_data["planned_count[]"] = ["4"]

    def read_settings():
        with app.app_context():
            db = get_session()
            try:
                department_row = db.execute(
                    text(
                        "SELECT resident_count_fixed, notes FROM departments "
                        "WHERE id=:department_id"
                    ),
                    {"department_id": department["id"]},
                ).one()
                planned_count = db.execute(
                    text(
                        "SELECT default_count FROM department_diet_defaults "
                        "WHERE department_id=:department_id AND diet_type_id=:diet_id"
                    ),
                    {
                        "department_id": department["id"],
                        "diet_id": diet_id,
                    },
                ).scalar_one()
                return department_row[0], department_row[1], planned_count
            finally:
                db.close()

    initial_values = read_settings()
    missing_token_form = {
        key: value for key, value in form_data.items() if key != "csrf_token"
    }
    missing_token = client.post(settings_path, data=missing_token_form)
    assert missing_token.status_code == 403
    assert missing_token.get_json()["detail"] == "csrf_missing"
    assert read_settings() == initial_values

    invalid_token_form = {**form_data, "csrf_token": "invalid-browser-form-token"}
    invalid_token = client.post(settings_path, data=invalid_token_form)
    assert invalid_token.status_code == 403
    assert invalid_token.get_json()["detail"] == "csrf_invalid"
    assert read_settings() == initial_values

    saved = client.post(settings_path, data=form_data)
    assert saved.status_code == 302
    assert read_settings() == (15, "Saved from rendered browser form", 4)
