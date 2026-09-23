from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit

import pytest

from core.app_factory import create_app
from core.db import get_session
from core.planera_product2_page2_context import build_product2_page2_planning_context
from scripts.seed_product2_e2e import MAIN_DB_PATH, BUILDER_DB_PATH, SITE_ID, YEAR, WEEK, SERVICE_DATE


def _python_executable() -> str:
    return str(Path(sys.executable))


def _seed_script_path() -> Path:
    return Path(__file__).resolve().parents[2] / "scripts" / "seed_product2_e2e.py"


def _load_counts() -> dict[str, int]:
    from sqlalchemy import text

    db = get_session()
    try:
        counts = {
            "departments": int(db.execute(text("SELECT COUNT(*) FROM departments WHERE site_id=:site_id"), {"site_id": SITE_ID}).scalar() or 0),
            "dietary_types": int(db.execute(text("SELECT COUNT(*) FROM dietary_types WHERE site_id=:site_id"), {"site_id": SITE_ID}).scalar() or 0),
            "groups": int(db.execute(text("SELECT COUNT(*) FROM department_requirement_groups g JOIN departments d ON d.id = g.department_id WHERE d.site_id=:site_id"), {"site_id": SITE_ID}).scalar() or 0),
            "zero_group_departments": int(db.execute(text("SELECT COUNT(*) FROM (SELECT d.id FROM departments d LEFT JOIN department_requirement_groups g ON g.department_id = d.id WHERE d.site_id=:site_id GROUP BY d.id HAVING COUNT(g.id)=0) x"), {"site_id": SITE_ID}).scalar() or 0),
            "multi_group_departments": int(db.execute(text("SELECT COUNT(*) FROM (SELECT d.id FROM departments d JOIN department_requirement_groups g ON g.department_id = d.id WHERE d.site_id=:site_id GROUP BY d.id HAVING COUNT(g.id) > 1) x"), {"site_id": SITE_ID}).scalar() or 0),
            "multi_requirement_groups": int(db.execute(text("SELECT COUNT(*) FROM department_requirement_groups g JOIN (SELECT group_id, COUNT(*) c FROM department_requirement_group_requirements GROUP BY group_id HAVING COUNT(*) > 1) x ON x.group_id = g.id JOIN departments d ON d.id = g.department_id WHERE d.site_id=:site_id"), {"site_id": SITE_ID}).scalar() or 0),
            "choices": int(db.execute(text("SELECT COUNT(*) FROM department_menu_choices WHERE site_id=:site_id"), {"site_id": SITE_ID}).scalar() or 0),
            "publications": int(db.execute(text("SELECT COUNT(*) FROM commun_builder_publication_pins WHERE site_id=:site_id"), {"site_id": SITE_ID}).scalar() or 0),
            "overrides": int(db.execute(text("SELECT COUNT(*) FROM department_requirement_group_service_overrides o JOIN department_requirement_groups g ON g.id = o.group_id JOIN departments d ON d.id = g.department_id WHERE d.site_id=:site_id"), {"site_id": SITE_ID}).scalar() or 0),
            "baseline_total": int(db.execute(text("SELECT COALESCE(SUM(resident_count_fixed), 0) FROM departments WHERE site_id=:site_id"), {"site_id": SITE_ID}).scalar() or 0),
            "baseline_min": int(db.execute(text("SELECT COALESCE(MIN(resident_count_fixed), 0) FROM departments WHERE site_id=:site_id"), {"site_id": SITE_ID}).scalar() or 0),
            "baseline_max": int(db.execute(text("SELECT COALESCE(MAX(resident_count_fixed), 0) FROM departments WHERE site_id=:site_id"), {"site_id": SITE_ID}).scalar() or 0),
            "kitchen_users": int(db.execute(text("SELECT COUNT(*) FROM users WHERE lower(email)=:email AND role='kitchen'"), {"email": 'e2e.kitchen@yuplan.local'}).scalar() or 0),
            "kitchen_bindings": int(db.execute(text("SELECT COUNT(*) FROM kitchen_user_sites k JOIN users u ON u.id = k.user_id WHERE lower(u.email)=:email AND k.site_id=:site_id"), {"email": 'e2e.kitchen@yuplan.local', "site_id": SITE_ID}).scalar() or 0),
        }
        return counts
    finally:
        db.close()


def _extract_planera_lunch_href(html: str) -> str:
    class _PlaneraLunchLinkParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self._current_href: str | None = None
            self._current_text: list[str] = []
            self.href: str | None = None

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag.lower() == "a":
                self._current_href = dict(attrs).get("href")
                self._current_text = []

        def handle_data(self, data: str) -> None:
            if self._current_href is not None:
                self._current_text.append(data)

        def handle_endtag(self, tag: str) -> None:
            if tag.lower() == "a" and self._current_href is not None:
                text = "".join(self._current_text).strip()
                if text.startswith("Planera lunch"):
                    self.href = self._current_href
                self._current_href = None
                self._current_text = []

    parser = _PlaneraLunchLinkParser()
    parser.feed(html)
    assert parser.href is not None
    return parser.href


def _cleanup_seed_db_state() -> None:
    import core.db as core_db

    session_factory = getattr(core_db, "_SessionFactory", None)
    if session_factory is not None:
        try:
            session_factory.remove()
        except Exception:
            pass
    engine = getattr(core_db, "_engine", None)
    if engine is not None:
        try:
            engine.dispose()
        except Exception:
            pass


def _seed_via_subprocess(*, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": "local",
            "FLASK_ENV": "local",
            "DEPLOY_ENV": "local",
            "DATABASE_URL": f"sqlite:///{MAIN_DB_PATH.as_posix()}",
            "BUILDER_DB_PATH": str(BUILDER_DB_PATH),
        }
    )
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [_python_executable(), str(_seed_script_path())],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_seed_refuses_dev_db_and_production_like_env() -> None:
    result = _seed_via_subprocess(
        extra_env={
            "APP_ENV": "production",
            "DATABASE_URL": "sqlite:///dev.db",
        }
    )

    assert result.returncode != 0
    assert "Refusing to seed" in (result.stderr or result.stdout)


def test_seed_product2_e2e_builds_isolated_dataset(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = _seed_via_subprocess()

    assert result.returncode == 0, result.stderr or result.stdout
    assert MAIN_DB_PATH.exists()
    assert BUILDER_DB_PATH.exists()

    # Deterministic reseed should succeed cleanly and preserve the same counts.
    result_again = _seed_via_subprocess()
    assert result_again.returncode == 0, result_again.stderr or result_again.stdout

    try:
        app = create_app(
            {
                "TESTING": True,
                "database_url": f"sqlite:///{MAIN_DB_PATH.as_posix()}",
                "BUILDER_DB_PATH": str(BUILDER_DB_PATH),
            }
        )
        with app.app_context():
            counts = _load_counts()
            assert counts["departments"] == 18
            assert counts["dietary_types"] >= 6
            assert counts["groups"] == 18
            assert counts["baseline_min"] >= 5
            assert counts["baseline_max"] <= 12
            assert 120 <= counts["baseline_total"] <= 160
            assert counts["zero_group_departments"] >= 4
            assert counts["multi_group_departments"] >= 2
            assert counts["multi_requirement_groups"] >= 2
            assert counts["choices"] == 17
            assert counts["publications"] == 1
            assert 2 <= counts["overrides"] <= 4
            assert counts["kitchen_users"] == 1
            assert counts["kitchen_bindings"] == 1

            context = build_product2_page2_planning_context(
                tenant_id=1,
                site_id=SITE_ID,
                service_date=SERVICE_DATE,
                meal="lunch",
            )

            assert context.status == "ok"
            assert context.publication_identity is not None
            assert context.publication_identity.builder_menu_id == "yuplan-e2e-product2-week37"
            assert len(context.options) == 2
            assert [option.variant_type for option in context.options] == ["alt1", "alt2"]
            assert len(context.destinations) == 18
            assert len(context.requirement_groups) == 17
            assert all(dest.baseline_quantity <= 12 for dest in context.destinations)
            assert all(dest.baseline_quantity >= 5 for dest in context.destinations)

            destinations = {destination.display_name: destination for destination in context.destinations}
            assert destinations["Avdelning 01"].selected_option_id is not None
            assert destinations["Avdelning 11"].selected_option_id is not None
            assert destinations["Avdelning 18"].selected_option_id is None

            choice_sources = {destination.choice_source for destination in context.destinations}
            assert "explicit" in choice_sources
            assert "none" in choice_sources

            assigned_counts = {
                option.display_title: sum(1 for destination in context.destinations if destination.selected_option_id == option.option_id)
                for option in context.options
            }
            assert assigned_counts["Vardagsgryta med rotfrukter"] == 10
            assert assigned_counts["Ugnsbakad fisk med dill"] == 7

            for destination in context.destinations:
                requirement_total = sum(group.effective_quantity for group in context.requirement_groups if group.destination_id == destination.destination_id)
                assert requirement_total <= destination.baseline_quantity

            review_service = __import__("core.planning_option_review", fromlist=["PlanningOptionReviewService"]).PlanningOptionReviewService()
            for option in context.options:
                review_state = review_service.get_option_review_state(
                    tenant_id=1,
                    site_id=SITE_ID,
                    service_date=SERVICE_DATE,
                    meal="lunch",
                    option_id=option.option_id,
                )
                assert review_state.review_state == "UNREVIEWED"
                assert review_state.review_is_stale is False
                assert review_state.review_id is None

            total_choices = {destination.choice_source for destination in context.destinations}
            assert total_choices <= {"explicit", "none"}
    finally:
        _cleanup_seed_db_state()


def test_seed_product2_e2e_normal_html_auth_and_page_flow(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = _seed_via_subprocess()
    assert result.returncode == 0, result.stderr or result.stdout

    try:
        app = create_app(
            {
                "TESTING": True,
                "database_url": f"sqlite:///{MAIN_DB_PATH.as_posix()}",
                "BUILDER_DB_PATH": str(BUILDER_DB_PATH),
            }
        )
        with app.app_context():
            client = app.test_client()
            login_response = client.post(
                "/auth/login",
                data={"email": "e2e.kitchen@yuplan.local", "password": "e2e-kitchen-pass"},
                headers={"Accept": "text/html"},
                follow_redirects=False,
            )
            assert login_response.status_code == 302
            assert login_response.headers["Location"].endswith("/ui/kitchen")

            with client.session_transaction() as sess:
                assert sess["role"] == "kitchen"
                assert sess["tenant_id"] == 1
                assert sess["site_id"] == SITE_ID

            page1_url = f"/ui/kitchen/planering?ui=product2&site_id={SITE_ID}&year={YEAR}&week={WEEK}&day=1"
            page1_response = client.get(page1_url)
            assert page1_response.status_code == 200
            page1_html = page1_response.get_data(as_text=True)
            assert "Centralköket E2E" in page1_html
            assert "Vardagsgryta med rotfrukter" in page1_html
            assert "Ugnsbakad fisk med dill" in page1_html
            assert "Planera lunch" in page1_html

            href = _extract_planera_lunch_href(page1_html)
            assert href.startswith("/ui/kitchen/planering/day?ui=product2&site_id=")

            page2_response = client.get(href)
            assert page2_response.status_code == 200
            assert urlsplit(href).path == "/ui/kitchen/planering/day"
            assert urlsplit(href).query == f"ui=product2&site_id={SITE_ID}&date=2026-09-08&meal=lunch"

            page2_html = page2_response.get_data(as_text=True)
            assert "Centralköket E2E" in page2_html
            assert "preview" not in page2_html.lower()
            assert "legacy" not in page2_html.lower()

            context = build_product2_page2_planning_context(
                tenant_id=1,
                site_id=SITE_ID,
                service_date=SERVICE_DATE,
                meal="lunch",
            )
            assert len(context.options) == 2
            assert len(context.destinations) == 18
            assert len(context.requirement_groups) == 17
            for option in context.options:
                review_state = __import__("core.planning_option_review", fromlist=["PlanningOptionReviewService"]).PlanningOptionReviewService().get_option_review_state(
                    tenant_id=1,
                    site_id=SITE_ID,
                    service_date=SERVICE_DATE,
                    meal="lunch",
                    option_id=option.option_id,
                )
                assert review_state.review_state == "UNREVIEWED"

            db = get_session()
            try:
                tenant_name = db.execute(
                    __import__("sqlalchemy", fromlist=["text"]).text("SELECT name FROM tenants WHERE id=:id"),
                    {"id": 1},
                ).scalar()
                assert tenant_name == "Yuplan E2E Kommun"
            finally:
                db.close()
    finally:
        _cleanup_seed_db_state()
