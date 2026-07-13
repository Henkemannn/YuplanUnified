from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from flask import current_app, has_app_context

from .commun_builder_linkage import CommunBuilderMenuLinkService
from .commun_builder_publication import CommunBuilderPublicationService
from .commun_builder_projection import CommunBuilderMenuProjectionReader, get_shadow_projection_reader


@dataclass(frozen=True)
class CommunBuilderParityDifference:
    kind: str
    blocking: bool
    key: tuple[str, str, str] | None = None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CommunBuilderParityResult:
    tenant_id: int
    site_id: str
    year: int
    week: int
    legacy_available: bool
    builder_link_available: bool
    publication_pin_available: bool
    builder_projection_available: bool
    legacy_row_count: int
    builder_row_count: int
    status: str
    score: int
    go: bool
    reasons: list[str] = field(default_factory=list)
    blocking_differences: list[CommunBuilderParityDifference] = field(default_factory=list)
    non_blocking_differences: list[CommunBuilderParityDifference] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    text_mismatches: list[dict[str, Any]] = field(default_factory=list)
    slot_mismatches: list[dict[str, Any]] = field(default_factory=list)
    order_mismatches: list[dict[str, Any]] = field(default_factory=list)
    missing_in_builder: list[dict[str, Any]] = field(default_factory=list)
    missing_in_legacy: list[dict[str, Any]] = field(default_factory=list)
    version_state: dict[str, Any] = field(default_factory=dict)
    publication_state: str = "legacy_only"
    fallback_state: str = "legacy"
    latest_builder_version: int | None = None
    published_builder_version: int | None = None
    legacy_menu_id: int | None = None
    builder_menu_id: str | None = None


@dataclass(frozen=True)
class CommunBuilderParityInventoryItem:
    area: str = ""
    file: str = ""
    service: str = ""
    path: str = ""
    function: str = ""
    data_source: str = ""
    io_type: str = ""
    feature_flag: str | None = None
    fallback: str = ""
    production_critical: bool = False
    classification: str = ""
    retirement_prerequisite: str = ""
    movable_later: bool = False
    must_stay: bool = False


@dataclass(frozen=True)
class CommunBuilderParityGateDecision:
    go: bool
    reasons: list[str] = field(default_factory=list)


_DEPENDENCY_INVENTORY: tuple[CommunBuilderParityInventoryItem, ...] = (
    CommunBuilderParityInventoryItem(
        area="legacy model tables",
        file="core/models.py",
        service="Menu / MenuVariant / Dish",
        path="core/models.py",
        function="Menu / MenuVariant / Dish",
        data_source="legacy menu tables",
        io_type="read/write",
        feature_flag=None,
        fallback="none",
        production_critical=True,
        classification="DO NOT REMOVE",
        retirement_prerequisite="no active reads or writes, archive/export and migration plan approved",
        movable_later=False,
        must_stay=True,
    ),
    CommunBuilderParityInventoryItem(
        area="legacy menu service",
        file="core/menu_service.py",
        service="get_week_view / publish_menu / unpublish_menu",
        path="core/menu_service.py",
        function="get_week_view / publish_menu / unpublish_menu",
        data_source="legacy menu tables",
        io_type="read/write",
        feature_flag=None,
        fallback="none",
        production_critical=True,
        classification="DO NOT REMOVE",
        retirement_prerequisite="all consumers moved and historical weeks handled elsewhere",
        movable_later=False,
        must_stay=True,
    ),
    CommunBuilderParityInventoryItem(
        area="legacy menu choice status",
        file="core/menu_choice_status.py",
        service="get_published_weeks / completion",
        path="core/menu_choice_status.py",
        function="get_published_weeks / completion",
        data_source="legacy menus.status",
        io_type="read/write",
        feature_flag=None,
        fallback="legacy status semantics",
        production_critical=True,
        classification="KEEP NOW",
        retirement_prerequisite="menu status consumers no longer read legacy rows",
        movable_later=False,
        must_stay=True,
    ),
    CommunBuilderParityInventoryItem(
        area="legacy weekview reads",
        file="core/weekview/service.py",
        service="fetch_weekview / toggle marks",
        path="core/weekview/service.py",
        function="fetch_weekview / toggle marks",
        data_source="legacy weekview tables",
        io_type="read/write",
        feature_flag=None,
        fallback="legacy weekview payload",
        production_critical=True,
        classification="KEEP NOW",
        retirement_prerequisite="weekview parity stable for all consumers",
        movable_later=False,
        must_stay=True,
    ),
    CommunBuilderParityInventoryItem(
        area="admin DOCX import",
        file="core/import_api.py",
        service="POST /import/docx",
        path="core/import_api.py",
        function="POST /import/docx",
        data_source="DOCX importer",
        io_type="write",
        feature_flag=None,
        fallback="legacy import behavior",
        production_critical=True,
        classification="KEEP NOW",
        retirement_prerequisite="canonical import produces identical Builder rows",
        movable_later=True,
        must_stay=True,
    ),
    CommunBuilderParityInventoryItem(
        area="admin Excel import",
        file="core/import_api.py",
        service="POST /import/xlsx",
        path="core/import_api.py",
        function="POST /import/xlsx",
        data_source="XLSX importer",
        io_type="write",
        feature_flag=None,
        fallback="legacy import behavior",
        production_critical=True,
        classification="KEEP NOW",
        retirement_prerequisite="canonical import produces identical Builder rows",
        movable_later=True,
        must_stay=True,
    ),
    CommunBuilderParityInventoryItem(
        area="builder import",
        file="core/import_api.py",
        service="POST /import/menu",
        path="core/import_api.py",
        function="POST /import/menu",
        data_source="legacy importer + builder canonical pilot",
        io_type="write",
        feature_flag="commun.builder.canonical_import_v0",
        fallback="legacy preview/import path",
        production_critical=False,
        classification="LATER WRITE RETIREMENT",
        retirement_prerequisite="production canonical import writes Builder and rollback is tested",
        movable_later=True,
        must_stay=True,
    ),
    CommunBuilderParityInventoryItem(
        area="builder linkage",
        file="core/commun_builder_linkage.py",
        service="create_or_replace_link / get_link_for_week / delete_link",
        path="core/commun_builder_linkage.py",
        function="create_or_replace_link / get_link_for_week / delete_link",
        data_source="builder menu links + legacy menu metadata",
        io_type="read/write",
        feature_flag="commun.builder.linkage_v0",
        fallback="legacy menu flow without durable Builder linkage",
        production_critical=False,
        classification="KEEP NOW",
        retirement_prerequisite="durable Builder linkage is no longer needed by any consumer",
        movable_later=True,
        must_stay=True,
    ),
    CommunBuilderParityInventoryItem(
        area="shadow reader",
        file="core/commun_builder_projection.py",
        service="shadow reader / compare_with_legacy",
        path="core/commun_builder_projection.py",
        function="shadow reader / compare_with_legacy",
        data_source="builder link + builder menu",
        io_type="read",
        feature_flag="commun.builder.projection_shadow_v0",
        fallback="legacy comparison",
        production_critical=False,
        classification="NEXT READ CANDIDATE",
        retirement_prerequisite="projection monitor is stable and text drift is understood",
        movable_later=True,
        must_stay=True,
    ),
    CommunBuilderParityInventoryItem(
        area="publication pin",
        file="core/commun_builder_publication.py",
        service="publication pin service",
        path="core/commun_builder_publication.py",
        function="publication pin service",
        data_source="builder link + pin store",
        io_type="write",
        feature_flag=None,
        fallback="legacy published status",
        production_critical=False,
        classification="LATER WRITE RETIREMENT",
        retirement_prerequisite="pinning is durable in drift, replay, and rollback",
        movable_later=True,
        must_stay=True,
    ),
    CommunBuilderParityInventoryItem(
        area="consumer pilot",
        file="core/ui_blueprint.py",
        service="/ui/weekview_overview",
        path="core/ui_blueprint.py",
        function="/ui/weekview_overview",
        data_source="legacy week payload + builder reader pilot",
        io_type="read",
        feature_flag="commun.builder.reader_v0",
        fallback="legacy payload",
        production_critical=False,
        classification="NEXT READ CANDIDATE",
        retirement_prerequisite="parity gate stable and fallback period completed",
        movable_later=True,
        must_stay=True,
    ),
    CommunBuilderParityInventoryItem(
        area="builder UI",
        file="core/builder_api.py",
        service="Builder UI / output / print",
        path="core/builder_api.py",
        function="Builder UI / output / print",
        data_source="Builder canonical store",
        io_type="read/write",
        feature_flag=None,
        fallback="Builder UI itself",
        production_critical=False,
        classification="KEEP NOW",
        retirement_prerequisite="builder canonical flows are the production source of truth",
        movable_later=False,
        must_stay=True,
    ),
    CommunBuilderParityInventoryItem(
        area="portal",
        file="core/ui_blueprint.py",
        service="portal_week / portal pages",
        path="core/ui_blueprint.py",
        function="portal",
        data_source="legacy portal payloads",
        io_type="read",
        feature_flag=None,
        fallback="legacy portal",
        production_critical=False,
        classification="DO NOT REMOVE",
        retirement_prerequisite="portal consumers have a new canonical path and history is archived",
        movable_later=False,
        must_stay=True,
    ),
    CommunBuilderParityInventoryItem(
        area="Planera",
        file="core/planera_api.py",
        service="planera API",
        path="core/planera_api.py",
        function="Planera API",
        data_source="legacy Planera input + comparison",
        io_type="read/write",
        feature_flag="ff.planera.enabled",
        fallback="legacy planera behavior",
        production_critical=False,
        classification="NEXT READ CANDIDATE",
        retirement_prerequisite="Planera consumers have Builder-backed input parity",
        movable_later=True,
        must_stay=True,
    ),
    CommunBuilderParityInventoryItem(
        area="reports",
        file="core/report_api.py",
        service="report API",
        path="core/report_api.py",
        function="report API",
        data_source="legacy report aggregates",
        io_type="read",
        feature_flag=None,
        fallback="legacy report output",
        production_critical=False,
        classification="NEXT READ CANDIDATE",
        retirement_prerequisite="report output can be produced from Builder canonical data",
        movable_later=True,
        must_stay=True,
    ),
    CommunBuilderParityInventoryItem(
        area="dashboard",
        file="core/dashboard_ui.py",
        service="dashboard UI",
        path="core/dashboard_ui.py",
        function="dashboard UI",
        data_source="legacy dashboard payloads",
        io_type="read",
        feature_flag=None,
        fallback="legacy dashboard",
        production_critical=False,
        classification="NEXT READ CANDIDATE",
        retirement_prerequisite="dashboard reads are parity-verified",
        movable_later=True,
        must_stay=True,
    ),
)

_ROLLBACK_RUNBOOK = {
    "commun.builder.reader_v0": {
        "disable": True,
        "fallback": "legacy reader",
        "verify": ["admin weekview overview renders legacy payload", "parity evaluator returns legacy_only or no builder path"],
    },
    "commun.builder.canonical_import_v0": {
        "disable": True,
        "fallback": "legacy /import/menu behavior",
        "verify": ["import/menu returns legacy preview contract", "no builder link updates are created"],
    },
    "commun.builder.projection_shadow_v0": {
        "disable": True,
        "fallback": "legacy compare-only path",
        "verify": ["shadow logs stop", "legacy payload stays unchanged"],
    },
    "commun.builder.linkage_v0": {
        "disable": True,
        "fallback": "legacy menu flow without Builder linkage",
        "verify": ["legacy menu views still load", "builder link creation stays disabled"],
    },
}

_RETIREMENT_PREREQUISITES = {
    "legacy_read_path": [
        "all selected consumers use Builder projection",
        "published pinning is stable",
        "fallback period is complete",
        "monitoring shows parity",
    ],
    "legacy_write_path": [
        "production canonical import writes Builder first",
        "rollback path exists and is tested",
        "legacy consumers are removed or shadowed",
        "historical compatibility is solved",
    ],
    "legacy_tables": [
        "no remaining reads",
        "no remaining writes",
        "archive/export plan exists",
        "historical reporting dependencies are retired",
    ],
}

_NEXT_CONSUMER_RECOMMENDATION = {
    "consumer": "admin menu import week preview",
    "route": "/ui/admin/menu-import/week/<year>/<week>",
    "service": "admin.ui_blueprint.admin_menu_import_week",
    "risk": "low",
    "payload": "existing admin week preview payload",
    "fallback": "legacy preview render",
    "feature_flag": None,
    "tests_required": [
        "legacy payload deep equality",
        "publication pin mismatch fallback",
        "tenant/site isolation",
    ],
}

# Only warnings that preserve the selected consumer payload may be non-blocking.
ALLOWED_NON_BLOCKING_WARNINGS = frozenset(
    {
        "canonical_name_differs_from_legacy_text",
    }
)


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


class CommunBuilderParityEvaluator:
    def __init__(self) -> None:
        self._link_service = CommunBuilderMenuLinkService()
        self._publication_service = CommunBuilderPublicationService()
        self._projection_reader = CommunBuilderMenuProjectionReader()

    def _warnings_allowed(self, warnings: list[str], allowed_warning_codes: Iterable[str] | None = None) -> bool:
        allowed_codes = set(allowed_warning_codes or ALLOWED_NON_BLOCKING_WARNINGS)
        return all(str(code) in allowed_codes for code in warnings)

    def evaluate_week(self, tenant_id: int, site_id: str, year: int, week: int) -> CommunBuilderParityResult:
        reasons: list[str] = []
        warnings: list[str] = []
        blocking: list[CommunBuilderParityDifference] = []
        non_blocking: list[CommunBuilderParityDifference] = []
        status = "legacy_only"
        fallback_state = "legacy"
        publication_state = "legacy_only"
        legacy_payload: dict[str, Any] | None = None
        legacy_error: str | None = None
        comparison = None
        projection = None
        legacy_row_count = 0
        builder_row_count = 0
        latest_builder_version: int | None = None
        published_builder_version: int | None = None
        legacy_menu_id: int | None = None
        builder_menu_id: str | None = None
        legacy_available = False
        builder_link_available = False
        publication_pin_available = False
        builder_projection_available = False

        try:
            legacy_payload = current_app.menu_service.get_week_view(int(tenant_id), str(site_id), int(week), int(year))
            legacy_available = True
            legacy_row_count = len(self._legacy_rows(legacy_payload))
            legacy_menu_id = self._legacy_menu_id(legacy_payload)
        except Exception as exc:
            legacy_error = str(exc)
            reasons.append(f"legacy_unavailable:{exc}")

        try:
            link = self._link_service.get_link_for_week(
                tenant_id=int(tenant_id),
                site_id=str(site_id),
                year=int(year),
                week=int(week),
            )
            builder_link_available = link is not None
            if link is not None:
                builder_menu_id = str(link.builder_menu_id)
                latest_builder_version = int(link.builder_menu_version)
        except ValueError as exc:
            reasons.append(f"tenant_site_mismatch:{exc}")
            return self._finalize(
                tenant_id=tenant_id,
                site_id=site_id,
                year=year,
                week=week,
                legacy_available=legacy_available,
                builder_link_available=False,
                publication_pin_available=False,
                builder_projection_available=False,
                legacy_row_count=legacy_row_count,
                builder_row_count=0,
                status="blocked",
                score=0,
                go=False,
                reasons=reasons,
                blocking=blocking + [CommunBuilderParityDifference(kind="tenant_site_mismatch", blocking=True, detail={"error": str(exc)})],
                non_blocking=non_blocking,
                warnings=warnings,
                comparison=comparison,
                projection=projection,
                fallback_state="legacy",
                publication_state="builder_missing",
                latest_builder_version=latest_builder_version,
                published_builder_version=published_builder_version,
                legacy_menu_id=legacy_menu_id,
                builder_menu_id=builder_menu_id,
            )

        publication = self._publication_service.get_publication_for_week(
            tenant_id=int(tenant_id),
            site_id=str(site_id),
            year=int(year),
            week=int(week),
        )
        publication_pin_available = publication is not None
        if publication is not None:
            published_builder_version = int(publication.builder_menu_version)
            builder_menu_id = builder_menu_id or str(publication.builder_menu_id)

        if not legacy_available:
            return self._finalize(
                tenant_id=tenant_id,
                site_id=site_id,
                year=year,
                week=week,
                legacy_available=False,
                builder_link_available=builder_link_available,
                publication_pin_available=publication_pin_available,
                builder_projection_available=False,
                legacy_row_count=0,
                builder_row_count=0,
                status="blocked",
                score=0,
                go=False,
                reasons=reasons,
                blocking=blocking + [CommunBuilderParityDifference(kind="fallback_failure", blocking=True, detail={"error": legacy_error or "legacy_unavailable"})],
                non_blocking=non_blocking,
                warnings=warnings,
                comparison=comparison,
                projection=projection,
                fallback_state="legacy",
                publication_state="legacy_unavailable",
                latest_builder_version=latest_builder_version,
                published_builder_version=published_builder_version,
                legacy_menu_id=legacy_menu_id,
                builder_menu_id=builder_menu_id,
            )

        reader_enabled = _feature_enabled("commun.builder.reader_v0")
        if not reader_enabled:
            publication_state = self._publication_state(legacy_payload, publication, builder_link_available)
            return self._finalize(
                tenant_id=tenant_id,
                site_id=site_id,
                year=year,
                week=week,
                legacy_available=legacy_available,
                builder_link_available=builder_link_available,
                publication_pin_available=publication_pin_available,
                builder_projection_available=False,
                legacy_row_count=legacy_row_count,
                builder_row_count=0,
                status="legacy_only",
                score=0,
                go=False,
                reasons=reasons + ["reader_disabled"],
                blocking=blocking,
                non_blocking=non_blocking,
                warnings=warnings,
                comparison=comparison,
                projection=projection,
                fallback_state="legacy",
                publication_state=publication_state,
                latest_builder_version=latest_builder_version,
                published_builder_version=published_builder_version,
                legacy_menu_id=legacy_menu_id,
                builder_menu_id=builder_menu_id,
            )

        if not builder_link_available:
            publication_state = "no_link"
            reasons.append("no_link")
            return self._finalize(
                tenant_id=tenant_id,
                site_id=site_id,
                year=year,
                week=week,
                legacy_available=legacy_available,
                builder_link_available=False,
                publication_pin_available=publication_pin_available,
                builder_projection_available=False,
                legacy_row_count=legacy_row_count,
                builder_row_count=0,
                status="no_link",
                score=0,
                go=False,
                reasons=reasons,
                blocking=blocking,
                non_blocking=non_blocking,
                warnings=warnings,
                comparison=comparison,
                projection=projection,
                fallback_state="legacy",
                publication_state=publication_state,
                latest_builder_version=latest_builder_version,
                published_builder_version=published_builder_version,
                legacy_menu_id=legacy_menu_id,
                builder_menu_id=builder_menu_id,
            )

        if publication is None:
            if self._legacy_is_published(legacy_payload):
                status = "no_pin"
                publication_state = "no_pin"
                reasons.append("no_publication_pin")
            else:
                status = "not_published"
                publication_state = "not_published"
                reasons.append("legacy_unpublished")
            return self._finalize(
                tenant_id=tenant_id,
                site_id=site_id,
                year=year,
                week=week,
                legacy_available=legacy_available,
                builder_link_available=True,
                publication_pin_available=False,
                builder_projection_available=False,
                legacy_row_count=legacy_row_count,
                builder_row_count=0,
                status=status,
                score=0,
                go=False,
                reasons=reasons,
                blocking=blocking,
                non_blocking=non_blocking,
                warnings=warnings,
                comparison=comparison,
                projection=projection,
                fallback_state="legacy",
                publication_state=publication_state,
                latest_builder_version=latest_builder_version,
                published_builder_version=None,
                legacy_menu_id=legacy_menu_id,
                builder_menu_id=builder_menu_id,
            )

        if latest_builder_version is not None and published_builder_version is not None and latest_builder_version != published_builder_version:
            reasons.append("version_mismatch")
            publication_state = "version_mismatch"
            return self._finalize(
                tenant_id=tenant_id,
                site_id=site_id,
                year=year,
                week=week,
                legacy_available=legacy_available,
                builder_link_available=True,
                publication_pin_available=True,
                builder_projection_available=False,
                legacy_row_count=legacy_row_count,
                builder_row_count=0,
                status="version_mismatch",
                score=0,
                go=False,
                reasons=reasons,
                blocking=blocking + [CommunBuilderParityDifference(kind="version_mismatch", blocking=True, detail={"latest": latest_builder_version, "published": published_builder_version})],
                non_blocking=non_blocking,
                warnings=warnings,
                comparison=comparison,
                projection=projection,
                fallback_state="legacy",
                publication_state=publication_state,
                latest_builder_version=latest_builder_version,
                published_builder_version=published_builder_version,
                legacy_menu_id=legacy_menu_id,
                builder_menu_id=builder_menu_id,
            )

        try:
            projection = get_shadow_projection_reader().get_projection_for_pinned_menu(
                tenant_id=int(tenant_id),
                site_id=str(site_id),
                year=int(year),
                week=int(week),
                builder_menu_id=str(publication.builder_menu_id),
                builder_menu_version=int(publication.builder_menu_version),
            )
            builder_projection_available = projection.status == "ok" and projection.projection is not None
        except Exception as exc:
            reasons.append(f"projection_error:{exc}")
            publication_state = "projection_error"
            return self._finalize(
                tenant_id=tenant_id,
                site_id=site_id,
                year=year,
                week=week,
                legacy_available=legacy_available,
                builder_link_available=True,
                publication_pin_available=True,
                builder_projection_available=False,
                legacy_row_count=legacy_row_count,
                builder_row_count=0,
                status="projection_error",
                score=0,
                go=False,
                reasons=reasons,
                blocking=blocking + [CommunBuilderParityDifference(kind="projection_error", blocking=True, detail={"error": str(exc)})],
                non_blocking=non_blocking,
                warnings=warnings,
                comparison=comparison,
                projection=projection,
                fallback_state="legacy",
                publication_state=publication_state,
                latest_builder_version=latest_builder_version,
                published_builder_version=published_builder_version,
                legacy_menu_id=legacy_menu_id,
                builder_menu_id=builder_menu_id,
            )

        if not builder_projection_available or projection is None or projection.projection is None:
            error = getattr(projection, "error", None) if projection is not None else None
            if error == "builder_menu_not_found":
                publication_state = "builder_missing"
                reasons.append("builder_missing")
                status = "blocked"
            else:
                publication_state = "projection_error"
                reasons.append(str(error or "projection_error"))
                status = "projection_error"
            return self._finalize(
                tenant_id=tenant_id,
                site_id=site_id,
                year=year,
                week=week,
                legacy_available=legacy_available,
                builder_link_available=True,
                publication_pin_available=True,
                builder_projection_available=False,
                legacy_row_count=legacy_row_count,
                builder_row_count=0,
                status=status,
                score=0,
                go=False,
                reasons=reasons,
                blocking=blocking + [CommunBuilderParityDifference(kind=publication_state, blocking=True, detail={"error": getattr(projection, "error", None)})],
                non_blocking=non_blocking,
                warnings=warnings,
                comparison=comparison,
                projection=projection,
                fallback_state="legacy",
                publication_state=publication_state,
                latest_builder_version=latest_builder_version,
                published_builder_version=published_builder_version,
                legacy_menu_id=legacy_menu_id,
                builder_menu_id=builder_menu_id,
            )

        builder_row_count = len(projection.projection.rows)
        comparison = self._projection_reader.compare_with_legacy(
            tenant_id=int(tenant_id),
            site_id=str(site_id),
            year=int(year),
            week=int(week),
            legacy_weekview=legacy_payload or {},
        )
        builder_rows = list(projection.projection.rows)
        unresolved_rows = [row for row in builder_rows if not bool(row.resolved)]
        if unresolved_rows:
            warnings.append("unresolved_rows_present")
            non_blocking.append(
                CommunBuilderParityDifference(
                    kind="warning",
                    blocking=False,
                    detail={"unresolved_row_count": len(unresolved_rows)},
                )
            )

        if comparison.status == "match" and not comparison.difference_count:
            status = "match_with_warnings" if warnings else "match"
        elif comparison.difference_count and (comparison.missing_in_builder or comparison.missing_in_legacy):
            status = "blocked"
            blocking.extend(self._comparison_differences(comparison, structural_only=True))
        elif comparison.difference_count:
            status = "difference"
            blocking.extend(self._comparison_differences(comparison, structural_only=False))
        else:
            status = "difference"
            blocking.extend(self._comparison_differences(comparison, structural_only=False))

        publication_state = "published_current"
        score = 100 if status == "match" else 95 if status == "match_with_warnings" else 0
        go = status == "match" or (status == "match_with_warnings" and self._warnings_allowed(warnings))
        fallback_state = "builder" if go else "legacy"
        if not go and status in {"difference", "blocked"}:
            reasons.append("fallback_to_legacy")
        if status == "blocked" and not reasons:
            reasons.append("blocking_difference")

        return self._finalize(
            tenant_id=tenant_id,
            site_id=site_id,
            year=year,
            week=week,
            legacy_available=legacy_available,
            builder_link_available=True,
            publication_pin_available=True,
            builder_projection_available=True,
            legacy_row_count=legacy_row_count,
            builder_row_count=builder_row_count,
            status=status,
            score=score,
            go=go,
            reasons=reasons,
            blocking=blocking,
            non_blocking=non_blocking,
            warnings=warnings,
            comparison=comparison,
            projection=projection,
            fallback_state=fallback_state,
            publication_state=publication_state,
            latest_builder_version=latest_builder_version,
            published_builder_version=published_builder_version,
            legacy_menu_id=legacy_menu_id,
            builder_menu_id=builder_menu_id,
        )

    def evaluate_batch(self, items: Iterable[tuple[int, str, int, int]]) -> list[CommunBuilderParityResult]:
        return [self.evaluate_week(tenant_id=tenant_id, site_id=site_id, year=year, week=week) for tenant_id, site_id, year, week in items]

    def gate(
        self,
        result: CommunBuilderParityResult,
        *,
        allowed_warning_codes: Iterable[str] | None = None,
    ) -> CommunBuilderParityGateDecision:
        if result.blocking_differences:
            reasons = list(result.reasons) or ["blocking_differences"]
            return CommunBuilderParityGateDecision(go=False, reasons=reasons)
        if result.status == "match":
            return CommunBuilderParityGateDecision(go=True, reasons=[])
        if result.status == "match_with_warnings" and self._warnings_allowed(list(result.warnings), allowed_warning_codes):
            return CommunBuilderParityGateDecision(go=True, reasons=[])
        reasons = list(result.reasons) or [result.status]
        if result.warnings:
            reasons.append("warning_not_allowlisted")
        return CommunBuilderParityGateDecision(go=False, reasons=reasons)

    def get_warning_allowlist(self) -> list[str]:
        return sorted(ALLOWED_NON_BLOCKING_WARNINGS)

    def get_dependency_inventory(self) -> list[dict[str, Any]]:
        return [item.__dict__.copy() for item in _DEPENDENCY_INVENTORY]

    def get_retirement_prerequisites(self) -> dict[str, list[str]]:
        return {key: list(value) for key, value in _RETIREMENT_PREREQUISITES.items()}

    def recommend_next_consumer(self) -> dict[str, Any]:
        return dict(_NEXT_CONSUMER_RECOMMENDATION)

    def get_rollback_runbook(self) -> dict[str, Any]:
        return {key: dict(value) for key, value in _ROLLBACK_RUNBOOK.items()}

    def _comparison_differences(self, comparison, *, structural_only: bool) -> list[CommunBuilderParityDifference]:
        diffs: list[CommunBuilderParityDifference] = []
        for item in comparison.missing_in_builder:
            diffs.append(CommunBuilderParityDifference(kind="missing_in_builder", blocking=True, key=tuple(item.get("key") or ("", "", "")), detail=item))
        for item in comparison.missing_in_legacy:
            diffs.append(CommunBuilderParityDifference(kind="missing_in_legacy", blocking=True, key=tuple(item.get("key") or ("", "", "")), detail=item))
        for item in comparison.text_mismatches:
            diffs.append(CommunBuilderParityDifference(kind="text_mismatch", blocking=True, key=tuple(item.get("key") or ("", "", "")), detail=item))
        for item in comparison.order_mismatches:
            diffs.append(CommunBuilderParityDifference(kind="order_mismatch", blocking=True, key=tuple(item.get("key") or ("", "", "")), detail=item))
        for item in comparison.slot_mismatches:
            diffs.append(CommunBuilderParityDifference(kind="slot_mismatch", blocking=True, key=tuple(item.get("key") or ("", "", "")), detail=item))
        return diffs

    def _legacy_rows(self, legacy_weekview: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not legacy_weekview:
            return []
        if isinstance(legacy_weekview.get("rows"), list):
            return list(legacy_weekview.get("rows") or [])
        days = legacy_weekview.get("days") or {}
        rows: list[dict[str, Any]] = []
        for day, meals in (days or {}).items():
            for meal, variants in (meals or {}).items():
                for variant_type, info in (variants or {}).items():
                    rows.append({"day": day, "meal": meal, "variant_type": variant_type, "text": info.get("dish_name") if isinstance(info, dict) else ""})
        return rows

    def _legacy_menu_id(self, legacy_weekview: dict[str, Any] | None) -> int | None:
        try:
            value = (legacy_weekview or {}).get("menu_id")
            return int(value) if value is not None else None
        except Exception:
            return None

    def _legacy_is_published(self, legacy_weekview: dict[str, Any] | None) -> bool:
        payload = legacy_weekview or {}
        status = str(payload.get("status") or payload.get("menu_status") or "").strip().lower()
        return status == "published"

    def _publication_state(self, legacy_weekview: dict[str, Any] | None, publication, builder_link_available: bool) -> str:
        if publication is None:
            return "no_link" if not builder_link_available else ("no_pin" if self._legacy_is_published(legacy_weekview) else "not_published")
        if not builder_link_available:
            return "builder_missing"
        return "published_current"

    def _finalize(
        self,
        *,
        tenant_id: int,
        site_id: str,
        year: int,
        week: int,
        legacy_available: bool,
        builder_link_available: bool,
        publication_pin_available: bool,
        builder_projection_available: bool,
        legacy_row_count: int,
        builder_row_count: int,
        status: str,
        score: int,
        go: bool,
        reasons: list[str],
        blocking: list[CommunBuilderParityDifference],
        non_blocking: list[CommunBuilderParityDifference],
        warnings: list[str],
        comparison,
        projection,
        fallback_state: str,
        publication_state: str,
        latest_builder_version: int | None,
        published_builder_version: int | None,
        legacy_menu_id: int | None,
        builder_menu_id: str | None,
    ) -> CommunBuilderParityResult:
        result = CommunBuilderParityResult(
            tenant_id=int(tenant_id),
            site_id=str(site_id),
            year=int(year),
            week=int(week),
            legacy_available=bool(legacy_available),
            builder_link_available=bool(builder_link_available),
            publication_pin_available=bool(publication_pin_available),
            builder_projection_available=bool(builder_projection_available),
            legacy_row_count=int(legacy_row_count),
            builder_row_count=int(builder_row_count),
            status=str(status),
            score=int(score),
            go=bool(go),
            reasons=list(reasons),
            blocking_differences=list(blocking),
            non_blocking_differences=list(non_blocking),
            warnings=list(warnings),
            text_mismatches=list(getattr(comparison, "text_mismatches", []) or []),
            slot_mismatches=list(getattr(comparison, "slot_mismatches", []) or []),
            order_mismatches=list(getattr(comparison, "order_mismatches", []) or []),
            missing_in_builder=list(getattr(comparison, "missing_in_builder", []) or []),
            missing_in_legacy=list(getattr(comparison, "missing_in_legacy", []) or []),
            version_state={
                "latest_builder_version": latest_builder_version,
                "published_builder_version": published_builder_version,
                "linked_version": getattr(comparison, "linked_version", None),
                "current_version": getattr(comparison, "current_version", None),
            },
            publication_state=publication_state,
            fallback_state=fallback_state,
            latest_builder_version=latest_builder_version,
            published_builder_version=published_builder_version,
            legacy_menu_id=legacy_menu_id,
            builder_menu_id=builder_menu_id,
        )
        try:
            current_app.logger.info(
                {
                    "event": "commun_builder_parity_result",
                    "tenant_id": tenant_id,
                    "site_id": site_id,
                    "year": year,
                    "week": week,
                    "status": status,
                    "go": go,
                    "score": score,
                    "publication_state": publication_state,
                    "fallback_state": fallback_state,
                }
            )
        except Exception:
            pass
        return result
