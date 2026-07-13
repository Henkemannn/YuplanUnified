from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from .db import get_session
from .models import CommunBuilderMenuLink, CommunBuilderPublicationPin


@dataclass(frozen=True)
class CommunBuilderPublicationState:
    tenant_id: int
    site_id: str
    year: int
    week: int
    legacy_menu_id: int | None
    builder_menu_id: str
    builder_menu_version: int
    source: str


class CommunBuilderPublicationRepository:
    def get_publication_for_week(
        self,
        *,
        tenant_id: int,
        site_id: str,
        year: int,
        week: int,
        db: Session | None = None,
    ) -> CommunBuilderPublicationPin | None:
        owns_session = db is None
        db = db or get_session()
        try:
            return (
                db.query(CommunBuilderPublicationPin)
                .filter_by(tenant_id=tenant_id, site_id=site_id, year=year, week=week)
                .first()
            )
        finally:
            if owns_session:
                db.close()

    def upsert_publication(
        self,
        *,
        tenant_id: int,
        site_id: str,
        year: int,
        week: int,
        legacy_menu_id: int | None,
        builder_menu_id: str,
        builder_menu_version: int,
        source: str,
        db: Session | None = None,
    ) -> CommunBuilderPublicationPin:
        owns_session = db is None
        db = db or get_session()
        try:
            existing = (
                db.query(CommunBuilderPublicationPin)
                .filter_by(tenant_id=tenant_id, site_id=site_id, year=year, week=week)
                .first()
            )
            now = datetime.now(timezone.utc)
            if existing is None:
                pin = CommunBuilderPublicationPin(
                    tenant_id=tenant_id,
                    site_id=site_id,
                    year=year,
                    week=week,
                    legacy_menu_id=legacy_menu_id,
                    builder_menu_id=builder_menu_id,
                    builder_menu_version=builder_menu_version,
                    source=source,
                    created_at=now,
                    updated_at=now,
                )
                db.add(pin)
            else:
                existing.legacy_menu_id = legacy_menu_id
                existing.builder_menu_id = builder_menu_id
                existing.builder_menu_version = builder_menu_version
                existing.source = source
                existing.updated_at = now
                pin = existing
            db.flush()
            if owns_session:
                db.commit()
            db.refresh(pin)
            return pin
        finally:
            if owns_session:
                db.close()

    def delete_publication(self, *, tenant_id: int, site_id: str, year: int, week: int, db: Session | None = None) -> None:
        owns_session = db is None
        db = db or get_session()
        try:
            db.query(CommunBuilderPublicationPin).filter_by(
                tenant_id=tenant_id, site_id=site_id, year=year, week=week
            ).delete(synchronize_session=False)
            if owns_session:
                db.commit()
        finally:
            if owns_session:
                db.close()


class CommunBuilderPublicationService:
    def __init__(self, *, repository: CommunBuilderPublicationRepository | None = None) -> None:
        self._repository = repository or CommunBuilderPublicationRepository()

    def _verify_projection(self, *, tenant_id: int, site_id: str, year: int, week: int, builder_menu_id: str, builder_menu_version: int) -> None:
        from .commun_builder_projection import get_shadow_projection_reader

        outcome = get_shadow_projection_reader().get_projection_for_pinned_menu(
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
            builder_menu_id=builder_menu_id,
            builder_menu_version=builder_menu_version,
        )
        if outcome.status != "ok" or outcome.projection is None:
            raise RuntimeError(f"projection_verification_failed:{outcome.error or outcome.status}")
        if any(bool(row.error) for row in outcome.projection.rows):
            raise RuntimeError(f"projection_verification_failed:{outcome.error or 'row_error'}")

    def sync_from_legacy_menu(
        self,
        *,
        tenant_id: int,
        site_id: str,
        year: int,
        week: int,
        legacy_menu_id: int | None,
        db: Session | None = None,
        verify_projection: bool = True,
    ) -> CommunBuilderPublicationPin | None:
        from .commun_builder_linkage import CommunBuilderMenuLinkService

        link = CommunBuilderMenuLinkService().get_link_for_week(
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
        )
        if link is None:
            self._repository.delete_publication(tenant_id=tenant_id, site_id=site_id, year=year, week=week, db=db)
            return None
        if verify_projection:
            self._verify_projection(
                tenant_id=tenant_id,
                site_id=site_id,
                year=year,
                week=week,
                builder_menu_id=str(link.builder_menu_id),
                builder_menu_version=int(link.builder_menu_version),
            )
        return self._repository.upsert_publication(
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
            legacy_menu_id=legacy_menu_id,
            builder_menu_id=str(link.builder_menu_id),
            builder_menu_version=int(link.builder_menu_version),
            source=str(link.source or "pilot"),
            db=db,
        )

    def publish_week(
        self,
        *,
        tenant_id: int,
        site_id: str,
        year: int,
        week: int,
        legacy_menu_id: int | None,
        db: Session | None = None,
    ) -> CommunBuilderPublicationPin | None:
        return self.sync_from_legacy_menu(
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
            legacy_menu_id=legacy_menu_id,
            db=db,
            verify_projection=True,
        )

    def republish_week(
        self,
        *,
        tenant_id: int,
        site_id: str,
        year: int,
        week: int,
        legacy_menu_id: int | None,
        db: Session | None = None,
    ) -> CommunBuilderPublicationPin | None:
        existing = self._repository.get_publication_for_week(tenant_id=tenant_id, site_id=site_id, year=year, week=week, db=db)
        if existing is None:
            raise RuntimeError("publication_missing")
        return self.sync_from_legacy_menu(
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
            legacy_menu_id=legacy_menu_id,
            db=db,
            verify_projection=True,
        )

    def unpublish_week(self, *, tenant_id: int, site_id: str, year: int, week: int, db: Session | None = None) -> None:
        self._repository.delete_publication(tenant_id=tenant_id, site_id=site_id, year=year, week=week, db=db)

    def get_publication_for_week(self, *, tenant_id: int, site_id: str, year: int, week: int) -> CommunBuilderPublicationState | None:
        row = self._repository.get_publication_for_week(tenant_id=tenant_id, site_id=site_id, year=year, week=week)
        if row is None:
            return None
        return CommunBuilderPublicationState(
            tenant_id=int(row.tenant_id),
            site_id=str(row.site_id),
            year=int(row.year),
            week=int(row.week),
            legacy_menu_id=int(row.legacy_menu_id) if row.legacy_menu_id is not None else None,
            builder_menu_id=str(row.builder_menu_id),
            builder_menu_version=int(row.builder_menu_version),
            source=str(row.source),
        )
