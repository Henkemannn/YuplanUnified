from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from flask import current_app
from sqlalchemy.orm import Session

from .builder_sqlite import builder_transaction
from .db import get_session
from .models import CommunBuilderMenuLink, CommunBuilderPublicationPin, CommunBuilderPublicationRevision


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
    projection_snapshot_json: str | None


@dataclass(frozen=True)
class CommunBuilderPublicationRevisionState:
    tenant_id: int
    site_id: str
    year: int
    week: int
    legacy_menu_id: int | None
    builder_menu_id: str
    builder_menu_version: int
    source: str
    projection_snapshot_json: str | None


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

    def get_publication_revision_for_version(
        self,
        *,
        tenant_id: int,
        site_id: str,
        year: int,
        week: int,
        builder_menu_id: str,
        builder_menu_version: int,
        db: Session | None = None,
    ) -> CommunBuilderPublicationRevision | None:
        owns_session = db is None
        db = db or get_session()
        try:
            return (
                db.query(CommunBuilderPublicationRevision)
                .filter_by(
                    tenant_id=tenant_id,
                    site_id=site_id,
                    year=year,
                    week=week,
                    builder_menu_id=builder_menu_id,
                    builder_menu_version=builder_menu_version,
                )
                .one_or_none()
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
        projection_snapshot_json: str | None = None,
        db: Session | None = None,
    ) -> CommunBuilderPublicationPin:
        owns_session = db is None
        db = db or get_session()
        try:
            now = datetime.now(timezone.utc)
            revision_existing = (
                db.query(CommunBuilderPublicationRevision)
                .filter_by(
                    tenant_id=tenant_id,
                    site_id=site_id,
                    year=year,
                    week=week,
                    builder_menu_id=builder_menu_id,
                    builder_menu_version=builder_menu_version,
                )
                .first()
            )
            if revision_existing is None:
                revision = CommunBuilderPublicationRevision(
                    tenant_id=tenant_id,
                    site_id=site_id,
                    year=year,
                    week=week,
                    legacy_menu_id=legacy_menu_id,
                    builder_menu_id=builder_menu_id,
                    builder_menu_version=builder_menu_version,
                    source=source,
                    projection_snapshot_json=projection_snapshot_json,
                    created_at=now,
                    updated_at=now,
                )
                db.add(revision)
            else:
                if str(revision_existing.projection_snapshot_json or "") != str(projection_snapshot_json or ""):
                    raise RuntimeError("publication_revision_conflict")
                revision = revision_existing

            existing = (
                db.query(CommunBuilderPublicationPin)
                .filter_by(tenant_id=tenant_id, site_id=site_id, year=year, week=week)
                .first()
            )
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
                    projection_snapshot_json=projection_snapshot_json,
                    created_at=now,
                    updated_at=now,
                )
                db.add(pin)
            else:
                pin_matches = (
                    existing.legacy_menu_id == legacy_menu_id
                    and str(existing.builder_menu_id) == str(builder_menu_id)
                    and int(existing.builder_menu_version) == int(builder_menu_version)
                    and str(existing.source) == str(source)
                    and str(existing.projection_snapshot_json or "") == str(projection_snapshot_json or "")
                )
                if not pin_matches:
                    existing.legacy_menu_id = legacy_menu_id
                    existing.builder_menu_id = builder_menu_id
                    existing.builder_menu_version = builder_menu_version
                    existing.source = source
                    existing.projection_snapshot_json = projection_snapshot_json
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

        outcome = get_shadow_projection_reader().get_projection_for_builder_menu(
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

    def _capture_projection_snapshot(
        self,
        *,
        tenant_id: int,
        site_id: str,
        year: int,
        week: int,
        builder_menu_id: str,
        builder_menu_version: int,
    ) -> str:
        from .commun_builder_projection import get_shadow_projection_reader

        outcome = get_shadow_projection_reader().get_projection_for_builder_menu(
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
            builder_menu_id=builder_menu_id,
            builder_menu_version=builder_menu_version,
        )
        if outcome.status != "ok" or outcome.projection is None:
            raise RuntimeError(f"projection_capture_failed:{outcome.error or outcome.status}")
        rows_payload: list[dict[str, Any]] = []
        for row in outcome.projection.rows:
            rows_payload.append(
                {
                    "day": row.day,
                    "meal": row.meal,
                    "variant_type": row.variant_type,
                    "sort_order": int(row.sort_order),
                    "builder_menu_row_id": row.builder_menu_row_id,
                    "selection_group_id": row.selection_group_id,
                    "composition_id": row.composition_id,
                    "resolved": bool(row.resolved),
                    "text": row.text,
                    "unresolved_text": row.unresolved_text,
                    "error": row.error,
                }
            )
        snapshot = {
            "schema_version": 1,
            "tenant_id": int(outcome.projection.tenant_id),
            "site_id": str(outcome.projection.site_id),
            "year": int(outcome.projection.year),
            "week": int(outcome.projection.week),
            "builder_menu_id": str(outcome.projection.builder_menu_id),
            "builder_menu_version": int(outcome.projection.builder_menu_version),
            "builder_status": str(outcome.projection.builder_status),
            "projection_version": int(outcome.projection.projection_version),
            "source": str(outcome.projection.source),
            "rows": rows_payload,
        }
        return json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _snapshot_content_key(snapshot_json: str | None) -> str:
        try:
            snapshot = json.loads(str(snapshot_json or ""))
        except (TypeError, ValueError):
            return ""
        if not isinstance(snapshot, dict):
            return ""
        content = {
            "rows": snapshot.get("rows") if isinstance(snapshot.get("rows"), list) else [],
        }
        return json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _builder_db_path() -> str:
        path = str(current_app.config.get("BUILDER_DB_PATH") or "").strip()
        if not path:
            raise RuntimeError("builder_database_path_missing")
        return path

    def _current_builder_menu_version(
        self,
        *,
        tenant_id: int,
        site_id: str,
        year: int,
        week: int,
        builder_menu_id: str,
        linked_version: int,
    ) -> int:
        from .commun_builder_projection import get_shadow_projection_reader

        outcome = get_shadow_projection_reader().get_projection_for_builder_menu(
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
            builder_menu_id=builder_menu_id,
            builder_menu_version=linked_version,
        )
        current_version = int(outcome.current_version or 0)
        return current_version if current_version > 0 else int(linked_version)

    def _ensure_builder_menu_version(self, *, builder_menu_id: str, version: int) -> int:
        flow = current_app.extensions.get("builder_menu_context_flow")
        menu_service = getattr(flow, "_menu_service", None)
        menu_repository = getattr(menu_service, "_menu_repository", None)
        if menu_service is not None and not hasattr(menu_repository, "db_path"):
            menu = menu_service.get_menu(str(builder_menu_id))
            if menu is None:
                raise RuntimeError("builder_menu_missing")
            current_version = int(menu.version)
            if current_version < int(version):
                menu_service.update_menu(str(builder_menu_id), version=int(version))
                return int(version)
            return current_version

        with builder_transaction(self._builder_db_path()) as conn:
            row = conn.execute(
                "SELECT version FROM builder_menus WHERE menu_id = ?",
                (str(builder_menu_id),),
            ).fetchone()
            if row is None:
                raise RuntimeError("builder_menu_missing")
            current_version = int(row[0])
            if current_version < int(version):
                conn.execute(
                    "UPDATE builder_menus SET version = ? WHERE menu_id = ?",
                    (int(version), str(builder_menu_id)),
                )
                return int(version)
            return current_version

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

        owns_db = db is None
        db = db or get_session()
        link = CommunBuilderMenuLinkService().get_link_for_week(
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
        )
        if link is None:
            self._repository.delete_publication(tenant_id=tenant_id, site_id=site_id, year=year, week=week, db=db)
            if owns_db:
                db.commit()
                db.close()
            return None
        builder_menu_id = str(link.builder_menu_id)
        linked_version = int(link.builder_menu_version)
        current_builder_version = self._current_builder_menu_version(
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
            builder_menu_id=builder_menu_id,
            linked_version=linked_version,
        )
        source_version = max(linked_version, current_builder_version)
        if verify_projection:
            self._verify_projection(
                tenant_id=tenant_id,
                site_id=site_id,
                year=year,
                week=week,
                builder_menu_id=builder_menu_id,
                builder_menu_version=source_version,
            )
        projection_snapshot_json = self._capture_projection_snapshot(
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
            builder_menu_id=builder_menu_id,
            builder_menu_version=source_version,
        )
        candidate_key = self._snapshot_content_key(projection_snapshot_json)
        active = self._repository.get_publication_for_week(
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
            db=db,
        )
        historical = self._repository.get_publication_revision_for_version(
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
            builder_menu_id=builder_menu_id,
            builder_menu_version=source_version,
            db=db,
        )
        active_key = self._snapshot_content_key(active.projection_snapshot_json) if active else ""
        historical_key = self._snapshot_content_key(historical.projection_snapshot_json) if historical else ""
        prior_keys = {key for key in (active_key, historical_key) if key}
        content_changed = bool(prior_keys) and candidate_key not in prior_keys
        publication_version = linked_version
        if not content_changed and active is not None:
            projection_snapshot_json = active.projection_snapshot_json
        elif not content_changed and historical is not None:
            projection_snapshot_json = historical.projection_snapshot_json
        active_version = int(active.builder_menu_version) if active is not None else None
        needs_new_source_version = (
            content_changed
            and source_version <= linked_version
            and (active_version is None or active_version == linked_version)
        )
        if needs_new_source_version:
            publication_version = self._ensure_builder_menu_version(
                builder_menu_id=builder_menu_id,
                version=linked_version + 1,
            )
            projection_snapshot_json = self._capture_projection_snapshot(
                tenant_id=tenant_id,
                site_id=site_id,
                year=year,
                week=week,
                builder_menu_id=builder_menu_id,
                builder_menu_version=publication_version,
            )
        elif content_changed and source_version > linked_version:
            publication_version = source_version

        if publication_version != linked_version:
            db_link = (
                db.query(CommunBuilderMenuLink)
                .filter_by(
                    tenant_id=int(tenant_id),
                    site_id=str(site_id),
                    year=int(year),
                    week=int(week),
                )
                .one_or_none()
            )
            if db_link is None:
                raise RuntimeError("builder_menu_link_missing")
            db_link.builder_menu_version = int(publication_version)
            db_link.updated_at = datetime.now(timezone.utc)
        try:
            pin = self._repository.upsert_publication(
                tenant_id=tenant_id,
                site_id=site_id,
                year=year,
                week=week,
                legacy_menu_id=legacy_menu_id,
                builder_menu_id=builder_menu_id,
                builder_menu_version=int(publication_version),
                source=str(link.source or "pilot"),
                projection_snapshot_json=projection_snapshot_json,
                db=db,
            )
            if owns_db:
                db.commit()
            return pin
        except Exception:
            if owns_db:
                db.rollback()
            raise
        finally:
            if owns_db:
                db.close()

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
            projection_snapshot_json=str(row.projection_snapshot_json) if row.projection_snapshot_json is not None else None,
        )

    def get_publication_revision_for_version(
        self,
        *,
        tenant_id: int,
        site_id: str,
        year: int,
        week: int,
        builder_menu_id: str,
        builder_menu_version: int,
    ) -> CommunBuilderPublicationRevisionState | None:
        row = self._repository.get_publication_revision_for_version(
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
            builder_menu_id=builder_menu_id,
            builder_menu_version=builder_menu_version,
        )
        if row is None:
            return None
        return CommunBuilderPublicationRevisionState(
            tenant_id=int(row.tenant_id),
            site_id=str(row.site_id),
            year=int(row.year),
            week=int(row.week),
            legacy_menu_id=int(row.legacy_menu_id) if row.legacy_menu_id is not None else None,
            builder_menu_id=str(row.builder_menu_id),
            builder_menu_version=int(row.builder_menu_version),
            source=str(row.source),
            projection_snapshot_json=str(row.projection_snapshot_json) if row.projection_snapshot_json is not None else None,
        )
