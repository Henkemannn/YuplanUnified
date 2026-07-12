from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from flask import current_app, has_app_context

from .admin_repo import SitesRepo
from .db import get_session
from .models import CommunBuilderMenuLink
from .models import Menu
from .week_key import parse_week_key

ALLOWED_LINK_SOURCES = {"manual", "import", "migration", "pilot"}


@dataclass(frozen=True)
class CommunBuilderMenuLinkRequest:
    tenant_id: int
    site_id: str
    year: int
    week: int
    builder_menu_id: str
    builder_menu_version: int
    source: str = "manual"
    projection_version: int = 1
    legacy_menu_id: int | None = None


class CommunBuilderMenuLinkRepository:
    def get_link_for_week(
        self,
        db,
        *,
        tenant_id: int,
        site_id: str,
        year: int,
        week: int,
    ) -> CommunBuilderMenuLink | None:
        return (
            db.query(CommunBuilderMenuLink)
            .filter_by(
                tenant_id=int(tenant_id),
                site_id=str(site_id),
                year=int(year),
                week=int(week),
            )
            .one_or_none()
        )

    def upsert_link(self, db, request: CommunBuilderMenuLinkRequest) -> CommunBuilderMenuLink:
        existing = self.get_link_for_week(
            db,
            tenant_id=request.tenant_id,
            site_id=request.site_id,
            year=request.year,
            week=request.week,
        )
        now = datetime.now(UTC)
        if existing is None:
            link = CommunBuilderMenuLink(
                tenant_id=int(request.tenant_id),
                site_id=str(request.site_id),
                year=int(request.year),
                week=int(request.week),
                legacy_menu_id=request.legacy_menu_id,
                builder_menu_id=str(request.builder_menu_id),
                builder_menu_version=int(request.builder_menu_version),
                source=str(request.source).strip().lower(),
                projection_version=int(request.projection_version),
                created_at=now,
                updated_at=now,
            )
            db.add(link)
            db.flush()
            return link

        existing.builder_menu_id = str(request.builder_menu_id)
        existing.builder_menu_version = int(request.builder_menu_version)
        existing.source = str(request.source).strip().lower()
        existing.projection_version = int(request.projection_version)
        existing.updated_at = now
        if request.legacy_menu_id is not None:
            existing.legacy_menu_id = int(request.legacy_menu_id)
        db.flush()
        return existing

    def delete_link(self, db, *, tenant_id: int, site_id: str, year: int, week: int) -> bool:
        link = self.get_link_for_week(
            db,
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
        )
        if link is None:
            return False
        db.delete(link)
        db.flush()
        return True


class CommunBuilderMenuLinkService:
    def __init__(
        self,
        *,
        repository: CommunBuilderMenuLinkRepository | None = None,
        builder_menu_context_flow: Any | None = None,
        sites_repo: SitesRepo | None = None,
    ) -> None:
        self._repository = repository or CommunBuilderMenuLinkRepository()
        self._builder_menu_context_flow = builder_menu_context_flow
        self._sites_repo = sites_repo or SitesRepo()

    def create_or_replace_link(
        self,
        *,
        tenant_id: int,
        site_id: str,
        year: int,
        week: int,
        builder_menu_id: str,
        legacy_menu_id: int | None = None,
        source: str = "manual",
        projection_version: int = 1,
    ) -> CommunBuilderMenuLink:
        tenant_id_value = int(tenant_id)
        site_id_value = str(site_id or "").strip()
        builder_menu_id_value = str(builder_menu_id or "").strip()
        if not site_id_value:
            raise ValueError("site_id must be non-empty")
        if not builder_menu_id_value:
            raise ValueError("builder_menu_id must be non-empty")
        if int(year) <= 0:
            raise ValueError("year must be positive")
        if int(week) < 1 or int(week) > 53:
            raise ValueError("week must be between 1 and 53")

        source_value = str(source or "").strip().lower()
        if source_value not in ALLOWED_LINK_SOURCES:
            raise ValueError("source invalid")
        if int(projection_version) <= 0:
            raise ValueError("projection_version must be positive")

        self._validate_site_tenant_access(tenant_id_value, site_id_value)
        builder_menu = self._get_builder_menu(builder_menu_id_value)
        if str(getattr(builder_menu, "site_id", "") or "").strip() != site_id_value:
            raise ValueError("builder_menu_site_mismatch")
        builder_year, builder_week = parse_week_key(str(getattr(builder_menu, "week_key", "") or ""))
        if builder_year != int(year) or builder_week != int(week):
            raise ValueError("builder_menu_week_mismatch")
        builder_version = int(getattr(builder_menu, "version", 0) or 0)
        if builder_version <= 0:
            raise ValueError("builder_menu_version_invalid")

        legacy_menu_id_value = self._validate_legacy_menu(
            tenant_id=tenant_id_value,
            site_id=site_id_value,
            year=int(year),
            week=int(week),
            legacy_menu_id=legacy_menu_id,
        )

        db = get_session()
        try:
            request = CommunBuilderMenuLinkRequest(
                tenant_id=tenant_id_value,
                site_id=site_id_value,
                year=int(year),
                week=int(week),
                builder_menu_id=builder_menu_id_value,
                builder_menu_version=builder_version,
                source=source_value,
                projection_version=int(projection_version),
                legacy_menu_id=legacy_menu_id_value,
            )
            link = self._repository.upsert_link(db, request)
            db.commit()
            db.refresh(link)
            return link
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def get_link_for_week(
        self,
        *,
        tenant_id: int,
        site_id: str,
        year: int,
        week: int,
    ) -> CommunBuilderMenuLink | None:
        tenant_id_value = int(tenant_id)
        site_id_value = str(site_id or "").strip()
        if not site_id_value:
            raise ValueError("site_id must be non-empty")
        if int(year) <= 0:
            raise ValueError("year must be positive")
        if int(week) < 1 or int(week) > 53:
            raise ValueError("week must be between 1 and 53")

        self._validate_site_tenant_access(tenant_id_value, site_id_value)
        db = get_session()
        try:
            return self._repository.get_link_for_week(
                db,
                tenant_id=tenant_id_value,
                site_id=site_id_value,
                year=int(year),
                week=int(week),
            )
        finally:
            db.close()

    def delete_link(
        self,
        *,
        tenant_id: int,
        site_id: str,
        year: int,
        week: int,
    ) -> bool:
        tenant_id_value = int(tenant_id)
        site_id_value = str(site_id or "").strip()
        if not site_id_value:
            raise ValueError("site_id must be non-empty")
        if int(year) <= 0:
            raise ValueError("year must be positive")
        if int(week) < 1 or int(week) > 53:
            raise ValueError("week must be between 1 and 53")

        self._validate_site_tenant_access(tenant_id_value, site_id_value)
        db = get_session()
        try:
            removed = self._repository.delete_link(
                db,
                tenant_id=tenant_id_value,
                site_id=site_id_value,
                year=int(year),
                week=int(week),
            )
            db.commit()
            return removed
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _validate_site_tenant_access(self, tenant_id: int, site_id: str) -> None:
        sites = self._sites_repo.list_sites_for_tenant(tenant_id)
        if not any(str(site.get("id") or "").strip() == site_id for site in sites):
            raise ValueError("site_not_found_or_not_owned")

    def _get_builder_menu(self, builder_menu_id: str) -> Any:
        flow = self._builder_menu_context_flow
        if flow is None and has_app_context():
            flow = current_app.extensions.get("builder_menu_context_flow")
        if flow is None:
            raise RuntimeError("builder_menu_context_flow_unavailable")
        for menu in flow.list_menus():
            if str(getattr(menu, "menu_id", "") or "").strip() == builder_menu_id:
                return menu
        raise ValueError("builder_menu_not_found")

    def _validate_legacy_menu(
        self,
        *,
        tenant_id: int,
        site_id: str,
        year: int,
        week: int,
        legacy_menu_id: int | None,
    ) -> int | None:
        if legacy_menu_id is None:
            return None
        db = get_session()
        try:
            menu = db.query(Menu).filter_by(id=int(legacy_menu_id)).one_or_none()
        finally:
            db.close()
        if menu is None:
            raise ValueError("legacy_menu_not_found")
        if int(menu.tenant_id or 0) != int(tenant_id):
            raise ValueError("legacy_menu_tenant_mismatch")
        if str(menu.site_id or "").strip() != site_id:
            raise ValueError("legacy_menu_site_mismatch")
        if int(menu.year or 0) != int(year) or int(menu.week or 0) != int(week):
            raise ValueError("legacy_menu_week_mismatch")
        return int(legacy_menu_id)


__all__ = [
    "ALLOWED_LINK_SOURCES",
    "CommunBuilderMenuLinkRequest",
    "CommunBuilderMenuLinkRepository",
    "CommunBuilderMenuLinkService",
]