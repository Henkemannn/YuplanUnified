"""Admin UI menu ETag Phase 11 tests - Optimistic locking for menu operations."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import text

from core.builder import BuilderFlow
from core.builder.library_scope import ObjectScope
from core.builder_menu_context_flow import BuilderMenuContextFlow
from core.db import get_session
from core.components import (
    ComponentService,
    CompositionService,
    InMemoryComponentAliasRepository,
    InMemoryComponentRepository,
    InMemoryCompositionRepository,
    InMemoryRecipeIngredientLineRepository,
    InMemoryRecipeRepository,
)
from core.commun_builder_import import import_menu_result_to_builder_canonical
from core.importers.base import ImportedMenuItem, MenuImportResult, WeekImport
from core.menu import MenuService, InMemoryCompositionAliasRepository


ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


class _ObjectScopeRepository:
    def __init__(self) -> None:
        self.scopes: dict[tuple[str, str], ObjectScope] = {}

    def get_scope(self, object_type: str, object_id: str) -> ObjectScope | None:
        return self.scopes.get((object_type, object_id))

    def find_private_fork_id(
        self,
        object_type: str,
        source_object_id: str,
        *,
        tenant_id: int,
        owner_user_id: int,
    ) -> str | None:
        return None

    def set_scope(self, object_type: str, object_id: str, scope: ObjectScope) -> None:
        self.scopes[(object_type, object_id)] = scope

    def delete_scope(self, object_type: str, object_id: str) -> None:
        self.scopes.pop((object_type, object_id), None)


def _client_with_site(app, site_id: str):
    from core.db import get_session

    db = get_session()
    try:
        db.execute(
            text(
                "INSERT OR IGNORE INTO users "
                "(id, tenant_id, username, email, password_hash, role, is_active) "
                "VALUES (1, 1, 'etag-admin', 'etag-admin@example.test', "
                "'not-used', 'admin', 1)"
            )
        )
        db.execute(text("UPDATE users SET tenant_id=1, role='admin', is_active=1 WHERE id=1"))
        db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS kitchen_user_sites "
                "(user_id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL)"
            )
        )
        db.execute(text("DELETE FROM kitchen_user_sites WHERE user_id=1"))
        db.execute(
            text(
                "INSERT INTO kitchen_user_sites (user_id, tenant_id, site_id) "
                "VALUES (1, 1, :site_id)"
            ),
            {"site_id": site_id},
        )
        db.commit()
    finally:
        db.close()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["site_id"] = site_id
    return client


def _seed_canonical_builder_menu(app_session, *, site_id: str, year: int, week: int) -> None:
    with app_session.app_context():
        component_repository = InMemoryComponentRepository()
        composition_repository = InMemoryCompositionRepository()
        alias_repository = InMemoryCompositionAliasRepository()
        recipe_repository = InMemoryRecipeRepository()
        ingredient_repository = InMemoryRecipeIngredientLineRepository()
        scope_repository = _ObjectScopeRepository()

        builder_flow = BuilderFlow(
            component_service=ComponentService(repository=component_repository),
            composition_service=CompositionService(repository=composition_repository),
            composition_repository=composition_repository,
            alias_repository=alias_repository,
            component_alias_repository=InMemoryComponentAliasRepository(),
            object_scope_repository=scope_repository,
        )
        menu_context_flow = BuilderMenuContextFlow(
            menu_service=MenuService(composition_repository=composition_repository),
            composition_repository=composition_repository,
            alias_repository=alias_repository,
            recipe_repository=recipe_repository,
            ingredient_repository=ingredient_repository,
            library_flow=builder_flow,
        )
        app_session.extensions["builder_menu_context_flow"] = menu_context_flow
        app_session.extensions["builder_flow"] = builder_flow

        composition_service = CompositionService(repository=composition_repository)
        composition_service.create_composition(
            composition_id="comp_kottbullar",
            composition_name="Köttbullar",
        )
        scope_repository.set_scope(
            "composition",
            "comp_kottbullar",
            ObjectScope(
                tenant_id=1,
                owner_scope="site",
                owner_site_id=site_id,
                owner_user_id=None,
                visibility="site",
            ),
        )

        import_menu_result_to_builder_canonical(
            MenuImportResult(
                weeks=[
                    WeekImport(
                        year=year,
                        week=week,
                        items=[
                            ImportedMenuItem(
                                day="monday",
                                meal="lunch",
                                variant_type="alt1",
                                dish_name="Köttbullar",
                            )
                        ],
                    )
                ]
            ),
            tenant_id=1,
            site_id=site_id,
        )


@pytest.fixture
def seeded_menu_with_updated_at(app_session):
    """Seed database with test menu data including updated_at timestamp."""
    from core.db import get_session
    
    db = get_session()
    try:
        # Clean first
        db.execute(text("DELETE FROM menu_variants"))
        db.execute(text("DELETE FROM menus"))
        db.execute(text("DELETE FROM dishes"))
        db.commit()
        
        # Create menu for week 48/2025 with explicit updated_at
        now = datetime.now(timezone.utc)
        db.execute(
            text("INSERT OR REPLACE INTO sites (id, name, tenant_id, version) VALUES (:id, :name, :tid, 0)"),
            {"id": "site-etag", "name": "Site ETag", "tid": 1},
        )
        db.execute(
            text("""
                INSERT INTO menus (id, tenant_id, site_id, week, year, status, updated_at) 
                VALUES (:id, :tid, :sid, :week, :year, :status, :updated_at)
            """),
            {"id": 102, "tid": 1, "sid": "site-etag", "week": 48, "year": 2025, "status": "draft", "updated_at": now}
        )
        
        # Create a dish
        db.execute(
            text("INSERT INTO dishes (id, tenant_id, name) VALUES (:id, :tid, :name)"),
            {"id": 302, "tid": 1, "name": "Köttbullar"}
        )
        
        # Create menu variant
        db.execute(
            text("""
                INSERT INTO menu_variants (menu_id, day, meal, variant_type, dish_id)
                VALUES (:mid, :day, :meal, :vtype, :did)
            """),
            {"mid": 102, "day": "Måndag", "meal": "Lunch", "vtype": "alt1", "did": 302}
        )
        
        db.commit()
    finally:
        db.close()

    _seed_canonical_builder_menu(app_session, site_id="site-etag", year=2025, week=48)
    
    return app_session


def test_get_week_view_includes_etag_header(seeded_menu_with_updated_at):
    """Test that GET /week/<y>/<w> includes ETag in response headers."""
    client = _client_with_site(seeded_menu_with_updated_at, "site-etag")
    
    response = client.get("/ui/admin/menu-import/week/2025/48", headers=ADMIN_HEADERS)
    
    assert response.status_code == 200
    assert "ETag" in response.headers
    etag = response.headers.get("ETag")
    assert etag.startswith('W/"menu-102-')
    

def test_get_edit_includes_etag_in_viewmodel(seeded_menu_with_updated_at):
    """Test that GET /edit includes ETag in template context."""
    client = _client_with_site(seeded_menu_with_updated_at, "site-etag")
    
    response = client.get("/ui/admin/menu-import/week/2025/48/edit", headers=ADMIN_HEADERS)
    
    assert response.status_code == 200
    # Check that ETag hidden input exists
    assert b'name="_etag"' in response.data
    # Check that it has a value attribute (the ETag itself)
    assert b'value="W/' in response.data or b"value='W/" in response.data


def test_save_without_if_match_returns_412(seeded_menu_with_updated_at):
    """Test that POST /save without If-Match header returns 412 with ProblemDetails."""
    client = _client_with_site(seeded_menu_with_updated_at, "site-etag")
    
    form_data = {
        "Måndag_Lunch_alt1": "Fiskgratäng",
    }
    
    response = client.post(
        "/ui/admin/menu-import/week/2025/48/save",
        data=form_data,
        headers=ADMIN_HEADERS
    )
    
    # Should redirect with flash message since it's not AJAX
    assert response.status_code == 302
    # Follow redirect to see flash message
    response = client.get(response.location, headers=ADMIN_HEADERS)
    assert b"Konflikt:" in response.data


def test_save_with_wrong_etag_returns_412(seeded_menu_with_updated_at):
    """Test that POST /save with incorrect ETag returns 412."""
    client = _client_with_site(seeded_menu_with_updated_at, "site-etag")
    
    # Use wrong ETag
    wrong_etag = 'W/"menu-102-1234567890000"'
    
    form_data = {
        "_etag": wrong_etag,
        "Måndag_Lunch_alt1": "Fiskgratäng",
    }
    
    response = client.post(
        "/ui/admin/menu-import/week/2025/48/save",
        data=form_data,
        headers=ADMIN_HEADERS
    )
    
    assert response.status_code == 302
    response = client.get(response.location, headers=ADMIN_HEADERS)
    assert b"Konflikt:" in response.data


def test_save_with_correct_etag_succeeds(seeded_menu_with_updated_at):
    """Test that POST /save with correct ETag succeeds."""
    client = _client_with_site(seeded_menu_with_updated_at, "site-etag")
    
    # First get the current ETag
    get_response = client.get("/ui/admin/menu-import/week/2025/48", headers=ADMIN_HEADERS)
    etag = get_response.headers.get("ETag")
    
    form_data = {
        "_etag": etag,
        "Måndag_Lunch_alt1": "Fiskgratäng",
    }
    
    response = client.post(
        "/ui/admin/menu-import/week/2025/48/save",
        data=form_data,
        headers=ADMIN_HEADERS
    )
    
    assert response.status_code == 302
    # Follow redirect
    response = client.get(response.location, headers=ADMIN_HEADERS)
    assert response.status_code == 200
    assert b"Sparat" in response.data


def test_publish_without_etag_returns_412(seeded_menu_with_updated_at):
    """Test that POST /publish without ETag returns 412."""
    client = _client_with_site(seeded_menu_with_updated_at, "site-etag")
    
    response = client.post(
        "/ui/admin/menu-import/week/2025/48/publish",
        headers=ADMIN_HEADERS
    )
    
    assert response.status_code == 302
    response = client.get(response.location, headers=ADMIN_HEADERS)
    assert b"Konflikt:" in response.data


def test_publish_with_correct_etag_succeeds(seeded_menu_with_updated_at):
    """Test that POST /publish with correct ETag succeeds."""
    client = _client_with_site(seeded_menu_with_updated_at, "site-etag")
    
    # Get current ETag
    get_response = client.get("/ui/admin/menu-import/week/2025/48", headers=ADMIN_HEADERS)
    etag = get_response.headers.get("ETag")
    
    response = client.post(
        "/ui/admin/menu-import/week/2025/48/publish",
        data={"_etag": etag},
        headers=ADMIN_HEADERS
    )
    
    assert response.status_code == 302
    response = client.get(response.location, headers=ADMIN_HEADERS)
    assert b"publicerad" in response.data


def test_unpublish_without_etag_returns_412(seeded_menu_with_updated_at):
    """Test that POST /unpublish without ETag returns 412."""
    client = _client_with_site(seeded_menu_with_updated_at, "site-etag")
    
    # First publish the menu
    from core.db import get_session
    db = get_session()
    try:
        db.execute(
            text("UPDATE menus SET status='published' WHERE id=102")
        )
        db.commit()
    finally:
        db.close()
    
    response = client.post(
        "/ui/admin/menu-import/week/2025/48/unpublish",
        headers=ADMIN_HEADERS
    )
    
    assert response.status_code == 302
    response = client.get(response.location, headers=ADMIN_HEADERS)
    assert b"Konflikt:" in response.data


def test_unpublish_with_correct_etag_succeeds(seeded_menu_with_updated_at):
    """Test that POST /unpublish with correct ETag succeeds."""
    client = _client_with_site(seeded_menu_with_updated_at, "site-etag")
    
    # First publish the menu
    from core.db import get_session
    db = get_session()
    try:
        db.execute(
            text("UPDATE menus SET status='published' WHERE id=102")
        )
        db.commit()
    finally:
        db.close()
    
    # Get current ETag
    get_response = client.get("/ui/admin/menu-import/week/2025/48", headers=ADMIN_HEADERS)
    etag = get_response.headers.get("ETag")
    
    response = client.post(
        "/ui/admin/menu-import/week/2025/48/unpublish",
        data={"_etag": etag},
        headers=ADMIN_HEADERS
    )
    
    assert response.status_code == 302
    response = client.get(response.location, headers=ADMIN_HEADERS)
    assert b"utkast" in response.data


def test_etag_changes_after_save(seeded_menu_with_updated_at):
    """Test that ETag value changes after a successful save operation."""
    client = _client_with_site(seeded_menu_with_updated_at, "site-etag")
    
    # Get initial ETag
    response1 = client.get("/ui/admin/menu-import/week/2025/48", headers=ADMIN_HEADERS)
    etag1 = response1.headers.get("ETag")
    
    # Save changes
    form_data = {
        "_etag": etag1,
        "Måndag_Lunch_alt1": "Ny rätt",
    }
    
    response2 = client.post(
        "/ui/admin/menu-import/week/2025/48/save",
        data=form_data,
        headers=ADMIN_HEADERS
    )
    
    assert response2.status_code == 302
    
    # Get new ETag
    response3 = client.get("/ui/admin/menu-import/week/2025/48", headers=ADMIN_HEADERS)
    etag2 = response3.headers.get("ETag")
    
    # ETags should be different
    assert etag1 != etag2


def test_concurrent_edit_scenario(seeded_menu_with_updated_at):
    """Test concurrent edit scenario where second save detects conflict."""
    client = _client_with_site(seeded_menu_with_updated_at, "site-etag")
    
    # User A gets the page and ETag
    response_a = client.get("/ui/admin/menu-import/week/2025/48", headers=ADMIN_HEADERS)
    etag_a = response_a.headers.get("ETag")
    
    # User B gets the page and ETag (same ETag)
    response_b = client.get("/ui/admin/menu-import/week/2025/48", headers=ADMIN_HEADERS)
    etag_b = response_b.headers.get("ETag")
    
    assert etag_a == etag_b
    
    # User A saves first (succeeds)
    form_data_a = {
        "_etag": etag_a,
        "Måndag_Lunch_alt1": "User A's dish",
    }
    response_a_save = client.post(
        "/ui/admin/menu-import/week/2025/48/save",
        data=form_data_a,
        headers=ADMIN_HEADERS
    )
    assert response_a_save.status_code == 302
    
    # User B tries to save with old ETag (fails)
    form_data_b = {
        "_etag": etag_b,  # This is now stale
        "Måndag_Lunch_alt1": "User B's dish",
    }
    response_b_save = client.post(
        "/ui/admin/menu-import/week/2025/48/save",
        data=form_data_b,
        headers=ADMIN_HEADERS
    )
    
    assert response_b_save.status_code == 302
    response_b_redirect = client.get(response_b_save.location, headers=ADMIN_HEADERS)
    assert b"Konflikt:" in response_b_redirect.data


def test_edit_and_save_reject_foreign_same_tenant_and_cross_tenant_sites(
    seeded_menu_with_updated_at,
):
    client = _client_with_site(seeded_menu_with_updated_at, "site-etag")
    db = get_session()
    try:
        db.execute(
            text(
                "INSERT OR REPLACE INTO sites (id, name, tenant_id, version) "
                "VALUES ('site-edit-foreign', 'Foreign same tenant', 1, 0), "
                "('site-edit-other-tenant', 'Foreign tenant', 2, 0)"
            )
        )
        db.execute(
            text(
                "INSERT OR REPLACE INTO tenants (id, name, active) "
                "VALUES (2, 'Other tenant', 1)"
            )
        )
        db.execute(
            text(
                "INSERT OR REPLACE INTO menus "
                "(id, tenant_id, site_id, week, year, status, updated_at) "
                "VALUES (103, 1, 'site-edit-foreign', 48, 2025, 'draft', :updated), "
                "(104, 2, 'site-edit-other-tenant', 48, 2025, 'draft', :updated)"
            ),
            {"updated": datetime.now(timezone.utc)},
        )
        db.execute(
            text(
                "INSERT OR REPLACE INTO menu_variants "
                "(id, menu_id, day, meal, variant_type, dish_id) "
                "VALUES (1031, 103, 'Måndag', 'Lunch', 'alt1', NULL), "
                "(1041, 104, 'Måndag', 'Lunch', 'alt1', NULL)"
            )
        )
        db.commit()
    finally:
        db.close()

    def snapshot(menu_id: int) -> tuple:
        db = get_session()
        try:
            return (
                db.execute(
                    text("SELECT status, updated_at FROM menus WHERE id=:id"),
                    {"id": menu_id},
                ).one(),
                tuple(
                    db.execute(
                        text(
                            "SELECT day, meal, variant_type, dish_id "
                            "FROM menu_variants WHERE menu_id=:id ORDER BY id"
                        ),
                        {"id": menu_id},
                    ).fetchall()
                ),
            )
        finally:
            db.close()

    for foreign_site in ("site-edit-foreign", "site-edit-other-tenant"):
        before = snapshot(103 if foreign_site == "site-edit-foreign" else 104)
        edit = client.get(
            f"/ui/admin/menu-import/week/2025/48/edit?site_id={foreign_site}",
            headers=ADMIN_HEADERS,
        )
        assert edit.status_code == 403

        save = client.post(
            f"/ui/admin/menu-import/week/2025/48/save?site_id={foreign_site}",
            data={"_etag": "foreign-etag", "Måndag_Lunch_alt1": "Changed"},
            headers={**ADMIN_HEADERS, "X-Requested-With": "XMLHttpRequest"},
        )
        assert save.status_code == 403
        assert snapshot(103 if foreign_site == "site-edit-foreign" else 104) == before


def test_next_menu_updated_at_advances_at_least_one_millisecond(monkeypatch):
    from admin import ui_blueprint

    base = datetime(2025, 1, 1, 12, 0, 0, 123000, tzinfo=timezone.utc)

    class FrozenDatetime:
        @staticmethod
        def now(tz=None):
            return base

    monkeypatch.setattr(ui_blueprint, "datetime", FrozenDatetime)

    bumped = ui_blueprint._next_menu_updated_at(base)

    assert bumped >= base + timedelta(milliseconds=1)
