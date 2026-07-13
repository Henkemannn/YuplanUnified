from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from flask import current_app, has_app_context

from .commun_builder_parity import CommunBuilderParityEvaluator
from .commun_builder_publication import CommunBuilderPublicationService
from .commun_builder_projection import CommunBuilderMenuProjectionReader


@dataclass(frozen=True)
class AdminImportPreviewReadResult:
    source: str
    payload: dict[str, Any]
    parity_status: str | None = None
    fallback_reason: str | None = None
    builder_menu_id: str | None = None
    builder_menu_version: int | None = None
    published_builder_version: int | None = None


def _feature_enabled(name: str) -> bool:
    try:
        if not has_app_context():
            return False
        helper = getattr(current_app, "feature_enabled", None)
        if callable(helper):
            return bool(helper(name))
        registry = getattr(current_app, "feature_registry", None)
        return bool(registry.enabled(name)) if registry else False
    except Exception:
        return False


def _temporary_reader_override(enabled: bool):
    class _Override:
        def __enter__(self):
            if not has_app_context():
                self._registry = None
                self._had_flag = False
                self._original = None
                return self
            self._registry = getattr(current_app, "feature_registry", None)
            self._had_flag = bool(self._registry and self._registry.has("commun.builder.reader_v0"))
            self._original = bool(self._registry.enabled("commun.builder.reader_v0")) if self._had_flag else None
            if self._registry is not None and self._had_flag and self._original != enabled:
                self._registry.set("commun.builder.reader_v0", enabled)
            return self

        def __exit__(self, exc_type, exc, tb):
            if self._registry is not None and self._had_flag and self._original is not None:
                self._registry.set("commun.builder.reader_v0", self._original)

    return _Override()


def _projection_to_legacy_days(projection_rows) -> dict[str, dict[str, dict[str, dict[str, Any]]]] | None:
    days: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    seen: set[tuple[str, str, str]] = set()
    for row in projection_rows:
        if getattr(row, "error", None):
            return None
        if not bool(getattr(row, "resolved", False)):
            return None
        day = str(getattr(row, "day", "") or "").strip().lower()
        meal = str(getattr(row, "meal", "") or "").strip().lower()
        variant = str(getattr(row, "variant_type", "") or "").strip().lower()
        text = str(getattr(row, "text", "") or "").strip()
        if not day or meal not in {"lunch", "dinner"} or not variant or not text:
            return None
        key = (day, meal, variant)
        if key in seen:
            return None
        seen.add(key)
        days.setdefault(day, {}).setdefault(meal, {})[variant] = {"dish_name": text}
    return days


def read_admin_import_week_preview(
    *,
    tenant_id: int,
    site_id: str,
    year: int,
    week: int,
    legacy_preview: dict[str, Any],
) -> AdminImportPreviewReadResult:
    legacy_payload = dict(legacy_preview or {})
    if not _feature_enabled("commun.builder.admin_import_preview_reader_v0"):
        _log_preview(
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
            source="legacy",
            parity_status=None,
            fallback_reason="feature_flag_off",
            builder_menu_version=None,
            published_builder_version=None,
        )
        return AdminImportPreviewReadResult(source="legacy", payload=legacy_payload, fallback_reason="feature_flag_off")

    try:
        parity_evaluator = CommunBuilderParityEvaluator()
        with _temporary_reader_override(True):
            parity = parity_evaluator.evaluate_week(tenant_id=tenant_id, site_id=site_id, year=year, week=week)
        gate_decision = parity_evaluator.gate(parity)
    except Exception as exc:
        reason = f"parity_exception:{exc}"
        _log_preview(
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
            source="legacy",
            parity_status="parity_exception",
            fallback_reason=reason,
            builder_menu_version=None,
            published_builder_version=None,
        )
        return AdminImportPreviewReadResult(source="legacy", payload=legacy_payload, parity_status="parity_exception", fallback_reason=reason)
    if not gate_decision.go:
        fallback_reason = gate_decision.reasons[0] if gate_decision.reasons else parity.status
        _log_preview(
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
            source="legacy",
            parity_status=parity.status,
            fallback_reason=fallback_reason,
            builder_menu_version=parity.latest_builder_version,
            published_builder_version=parity.published_builder_version,
        )
        return AdminImportPreviewReadResult(
            source="legacy",
            payload=legacy_payload,
            parity_status=parity.status,
            fallback_reason=fallback_reason,
            builder_menu_version=parity.latest_builder_version,
            published_builder_version=parity.published_builder_version,
        )

    if str(legacy_payload.get("menu_status") or "").strip().lower() != "published":
        _log_preview(
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
            source="legacy",
            parity_status=parity.status,
            fallback_reason="draft_preview_legacy_only",
            builder_menu_version=parity.latest_builder_version,
            published_builder_version=parity.published_builder_version,
        )
        return AdminImportPreviewReadResult(
            source="legacy",
            payload=legacy_payload,
            parity_status=parity.status,
            fallback_reason="draft_preview_legacy_only",
            builder_menu_version=parity.latest_builder_version,
            published_builder_version=parity.published_builder_version,
        )

    try:
        publication_service = CommunBuilderPublicationService()
        publication = publication_service.get_publication_for_week(
            tenant_id=int(tenant_id),
            site_id=str(site_id),
            year=int(year),
            week=int(week),
        )
    except Exception as exc:
        reason = f"publication_lookup_exception:{exc}"
        _log_preview(
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
            source="legacy",
            parity_status=parity.status,
            fallback_reason=reason,
            builder_menu_version=parity.latest_builder_version,
            published_builder_version=parity.published_builder_version,
        )
        return AdminImportPreviewReadResult(
            source="legacy",
            payload=legacy_payload,
            parity_status=parity.status,
            fallback_reason=reason,
            builder_menu_version=parity.latest_builder_version,
            published_builder_version=parity.published_builder_version,
        )
    if publication is None:
        _log_preview(
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
            source="legacy",
            parity_status=parity.status,
            fallback_reason="no_publication_pin",
            builder_menu_version=parity.latest_builder_version,
            published_builder_version=None,
        )
        return AdminImportPreviewReadResult(
            source="legacy",
            payload=legacy_payload,
            parity_status=parity.status,
            fallback_reason="no_publication_pin",
            builder_menu_version=parity.latest_builder_version,
            published_builder_version=None,
        )

    reader = CommunBuilderMenuProjectionReader()
    try:
        projection_outcome = reader.get_projection_for_pinned_menu(
            tenant_id=int(tenant_id),
            site_id=str(site_id),
            year=int(year),
            week=int(week),
            builder_menu_id=str(publication.builder_menu_id),
            builder_menu_version=int(publication.builder_menu_version),
        )
    except Exception:
        _log_preview(
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
            source="legacy",
            parity_status=parity.status,
            fallback_reason="projection_exception",
            builder_menu_version=int(getattr(publication, "builder_menu_version", 0) or 0),
            published_builder_version=int(getattr(publication, "builder_menu_version", 0) or 0),
        )
        return AdminImportPreviewReadResult(
            source="legacy",
            payload=legacy_payload,
            parity_status=parity.status,
            fallback_reason="projection_exception",
            builder_menu_id=str(getattr(publication, "builder_menu_id", "") or "") or None,
            builder_menu_version=int(getattr(publication, "builder_menu_version", 0) or 0),
            published_builder_version=int(getattr(publication, "builder_menu_version", 0) or 0),
        )

    if projection_outcome.status != "ok" or projection_outcome.projection is None:
        reason = str(projection_outcome.error or projection_outcome.status or "projection_error")
        _log_preview(
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
            source="legacy",
            parity_status=parity.status,
            fallback_reason=reason,
            builder_menu_version=int(getattr(publication, "builder_menu_version", 0) or 0),
            published_builder_version=int(getattr(publication, "builder_menu_version", 0) or 0),
        )
        return AdminImportPreviewReadResult(
            source="legacy",
            payload=legacy_payload,
            parity_status=parity.status,
            fallback_reason=reason,
            builder_menu_id=str(publication.builder_menu_id),
            builder_menu_version=int(publication.builder_menu_version),
            published_builder_version=int(publication.builder_menu_version),
        )

    days = _projection_to_legacy_days(projection_outcome.projection.rows)
    if days is None:
        _log_preview(
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
            source="legacy",
            parity_status=parity.status,
            fallback_reason="adapter_failed",
            builder_menu_version=int(getattr(publication, "builder_menu_version", 0) or 0),
            published_builder_version=int(getattr(publication, "builder_menu_version", 0) or 0),
        )
        return AdminImportPreviewReadResult(
            source="legacy",
            payload=legacy_payload,
            parity_status=parity.status,
            fallback_reason="adapter_failed",
            builder_menu_id=str(publication.builder_menu_id),
            builder_menu_version=int(publication.builder_menu_version),
            published_builder_version=int(publication.builder_menu_version),
        )

    builder_payload = dict(legacy_payload)
    builder_payload["days"] = days
    _log_preview(
        tenant_id=tenant_id,
        site_id=site_id,
        year=year,
        week=week,
        source="builder",
        parity_status=parity.status,
        fallback_reason=None,
        builder_menu_version=int(publication.builder_menu_version),
        published_builder_version=int(publication.builder_menu_version),
    )
    return AdminImportPreviewReadResult(
        source="builder",
        payload=builder_payload,
        parity_status=parity.status,
        fallback_reason=None,
        builder_menu_id=str(publication.builder_menu_id),
        builder_menu_version=int(publication.builder_menu_version),
        published_builder_version=int(publication.builder_menu_version),
    )


def _log_preview(
    *,
    tenant_id: int,
    site_id: str,
    year: int,
    week: int,
    source: str,
    parity_status: str | None,
    fallback_reason: str | None,
    builder_menu_version: int | None,
    published_builder_version: int | None,
) -> None:
    try:
        current_app.logger.info(
            {
                "event": "admin_import_preview_read",
                "consumer": "admin_import_preview",
                "tenant_id": int(tenant_id),
                "site_id": str(site_id),
                "year": int(year),
                "week": int(week),
                "reader_source": source,
                "parity_status": parity_status,
                "go": source == "builder",
                "fallback_reason": fallback_reason,
                "builder_menu_version": builder_menu_version,
                "published_builder_version": published_builder_version,
            }
        )
    except Exception:
        pass


__all__ = ["AdminImportPreviewReadResult", "read_admin_import_week_preview"]