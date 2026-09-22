from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date as _date, datetime as _datetime
import json
from hashlib import sha256
from typing import Any

from .db import get_session, get_site_tenant
from .models import PlanningOptionReview, PlanningOptionReviewDecision
from .planera_product2_page2_context import (
    Product2Page2DestinationVM,
    Product2Page2PlanningContext,
    Product2Page2PublicationIdentity,
    Product2Page2RequirementGroupVM,
    build_product2_page2_planning_context,
)


REVIEW_STATE_UNREVIEWED = "UNREVIEWED"
REVIEW_STATE_NO_DEVIATIONS = "REVIEWED_NO_DEVIATIONS"
REVIEW_STATE_WITH_DEVIATIONS = "REVIEWED_WITH_DEVIATIONS"

NO_ADAPTATION_REQUIRED = "NO_ADAPTATION_REQUIRED"
ADAPTATION_REQUIRED = "ADAPTATION_REQUIRED"
_BASIS_VERSION = 1


class PlanningOptionReviewError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PlanningOptionReviewDecisionInput:
    destination_id: str
    requirement_group_id: str
    decision: str


@dataclass(frozen=True, slots=True)
class PlanningOptionReviewDecisionState:
    destination_id: str
    requirement_group_id: str
    decision: str


@dataclass(frozen=True, slots=True)
class PlanningOptionReviewBasis:
    payload: dict[str, Any]
    review_basis_hash: str


@dataclass(frozen=True, slots=True)
class PlanningOptionReviewState:
    review_state: str
    review_is_stale: bool
    review_id: int | None
    review_basis_hash: str | None
    current_basis_hash: str | None
    reviewed_by_user_id: int | None
    reviewed_at: _datetime | None
    completed_at: _datetime | None
    relevant_group_count: int
    decision_count: int
    no_adaptation_count: int
    adaptation_count: int
    decisions: tuple[PlanningOptionReviewDecisionState, ...]


@dataclass(frozen=True, slots=True)
class _ResolvedOptionScope:
    context: Product2Page2PlanningContext
    publication_identity: Product2Page2PublicationIdentity | None
    option_id: str | None
    assigned_destinations: tuple[Product2Page2DestinationVM, ...]
    relevant_groups: tuple[Product2Page2RequirementGroupVM, ...]


def _normalize_tenant_id(value: object) -> int:
    tenant_id = int(value)
    if tenant_id <= 0:
        raise PlanningOptionReviewError("tenant_id_invalid")
    return tenant_id


def _normalize_site_id(value: object) -> str:
    site_id = str(value or "").strip()
    if not site_id:
        raise PlanningOptionReviewError("site_id_missing")
    return site_id


def _normalize_service_date(value: object) -> _date:
    if isinstance(value, _date):
        return value
    raw = str(value or "").strip()
    if not raw:
        raise PlanningOptionReviewError("service_date_missing")
    try:
        return _date.fromisoformat(raw)
    except Exception as exc:  # pragma: no cover - defensive normalization
        raise PlanningOptionReviewError("service_date_invalid") from exc


def _normalize_meal(value: object) -> str:
    meal = str(value or "").strip().lower()
    if meal != "lunch":
        raise PlanningOptionReviewError("meal_unsupported")
    return meal


def _normalize_option_id(value: object) -> str:
    option_id = str(value or "").strip()
    if not option_id:
        raise PlanningOptionReviewError("option_id_missing")
    return option_id


def _normalize_user_id(value: object) -> int:
    user_id = int(value)
    if user_id <= 0:
        raise PlanningOptionReviewError("reviewed_by_user_id_invalid")
    return user_id


def _normalize_decision_value(value: object) -> str:
    decision = str(value or "").strip().upper()
    if decision not in {NO_ADAPTATION_REQUIRED, ADAPTATION_REQUIRED}:
        raise PlanningOptionReviewError("decision_invalid")
    return decision


def _normalize_decision_item(item: object) -> PlanningOptionReviewDecisionInput:
    if isinstance(item, PlanningOptionReviewDecisionInput):
        return PlanningOptionReviewDecisionInput(
            destination_id=str(item.destination_id).strip(),
            requirement_group_id=str(item.requirement_group_id).strip(),
            decision=_normalize_decision_value(item.decision),
        )
    if isinstance(item, Mapping):
        destination_id = str(item.get("destination_id") or "").strip()
        requirement_group_id = str(item.get("requirement_group_id") or "").strip()
        decision = _normalize_decision_value(item.get("decision"))
        return PlanningOptionReviewDecisionInput(
            destination_id=destination_id,
            requirement_group_id=requirement_group_id,
            decision=decision,
        )
    destination_id = str(getattr(item, "destination_id", "") or "").strip()
    requirement_group_id = str(getattr(item, "requirement_group_id", "") or "").strip()
    decision = _normalize_decision_value(getattr(item, "decision", ""))
    return PlanningOptionReviewDecisionInput(
        destination_id=destination_id,
        requirement_group_id=requirement_group_id,
        decision=decision,
    )


def _sorted_requirement_payload(requirements: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    sorted_requirements = sorted(
        requirements,
        key=lambda requirement: (
            int(requirement.get("dietary_type_id") or 0),
            str(requirement.get("requirement_key") or ""),
            str(requirement.get("semantics") or ""),
        ),
    )
    return [
        {
            "dietary_type_id": int(requirement.get("dietary_type_id") or 0),
            "requirement_key": str(requirement.get("requirement_key") or "").strip() or None,
            "semantics": str(requirement.get("semantics") or "").strip() or None,
        }
        for requirement in sorted_requirements
    ]


def _current_year_week(service_date: _date) -> tuple[int, int]:
    iso_year, iso_week, _weekday = service_date.isocalendar()
    return int(iso_year), int(iso_week)


def build_option_review_basis_payload(
    *,
    tenant_id: int,
    site_id: str,
    service_date: _date,
    meal: str,
    publication_identity: Product2Page2PublicationIdentity,
    option_id: str,
    assigned_destinations: Iterable[Product2Page2DestinationVM],
    relevant_groups: Iterable[Product2Page2RequirementGroupVM],
) -> dict[str, Any]:
    assigned_destination_ids = sorted({str(destination.destination_id) for destination in assigned_destinations})
    grouped_requirements: list[dict[str, Any]] = []
    for group in sorted(
        relevant_groups,
        key=lambda item: (str(item.destination_id), str(item.requirement_group_id)),
    ):
        grouped_requirements.append(
            {
                "destination_id": str(group.destination_id),
                "requirement_group_id": str(group.requirement_group_id),
                "requirements": _sorted_requirement_payload(
                    {
                        "dietary_type_id": requirement.dietary_type_id,
                        "requirement_key": requirement.requirement_key,
                        "semantics": requirement.semantics,
                    }
                    for requirement in group.requirements
                ),
            }
        )
    return {
        "review_basis_version": _BASIS_VERSION,
        "tenant_id": int(tenant_id),
        "site_id": str(site_id),
        "service_date": service_date.isoformat(),
        "meal": str(meal),
        "builder_menu_id": str(publication_identity.builder_menu_id),
        "builder_menu_version": int(publication_identity.builder_menu_version),
        "builder_menu_row_id": str(option_id),
        "assigned_destination_ids": assigned_destination_ids,
        "relevant_groups": grouped_requirements,
    }


def compute_option_review_basis_hash(payload: dict[str, Any]) -> str:
    canonical_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(canonical_json.encode("utf-8")).hexdigest()


class PlanningOptionReviewService:
    def _ensure_tables(self, db) -> None:
        bind = getattr(db, "bind", None)
        if bind is None or getattr(getattr(bind, "dialect", None), "name", "") != "sqlite":
            return
        PlanningOptionReview.__table__.create(bind=bind, checkfirst=True)
        PlanningOptionReviewDecision.__table__.create(bind=bind, checkfirst=True)

    def _load_context(self, *, tenant_id: int, site_id: str, service_date: _date, meal: str) -> Product2Page2PlanningContext:
        return build_product2_page2_planning_context(
            tenant_id=tenant_id,
            site_id=site_id,
            service_date=service_date,
            meal=meal,
        )

    def _resolve_scope(self, *, context: Product2Page2PlanningContext, option_id: str) -> _ResolvedOptionScope:
        publication_identity = context.publication_identity
        if publication_identity is None or context.status != "ok":
            return _ResolvedOptionScope(context, publication_identity, None, (), ())
        normalized_option_id = _normalize_option_id(option_id)
        option = next((row for row in context.options if str(row.option_id) == normalized_option_id), None)
        if option is None:
            return _ResolvedOptionScope(context, publication_identity, None, (), ())
        assigned_destinations = tuple(
            destination for destination in context.destinations if str(destination.selected_option_id or "") == normalized_option_id
        )
        assigned_destination_ids = {destination.destination_id for destination in assigned_destinations}
        relevant_groups = tuple(
            group for group in context.requirement_groups if str(group.destination_id) in assigned_destination_ids
        )
        return _ResolvedOptionScope(context, publication_identity, normalized_option_id, assigned_destinations, relevant_groups)

    def _review_row_query(self, db, *, tenant_id: int, site_id: str, service_date: _date, meal: str, option_id: str):
        return (
            db.query(PlanningOptionReview)
            .filter_by(
                tenant_id=tenant_id,
                site_id=site_id,
                service_date=service_date,
                meal=meal,
                builder_menu_row_id=option_id,
            )
            .order_by(PlanningOptionReview.updated_at.desc(), PlanningOptionReview.id.desc())
        )

    def _load_review_row_exact(
        self,
        db,
        *,
        tenant_id: int,
        site_id: str,
        service_date: _date,
        meal: str,
        publication_identity: Product2Page2PublicationIdentity,
        option_id: str,
    ) -> PlanningOptionReview | None:
        return (
            db.query(PlanningOptionReview)
            .filter_by(
                tenant_id=tenant_id,
                site_id=site_id,
                service_date=service_date,
                meal=meal,
                builder_menu_id=str(publication_identity.builder_menu_id),
                builder_menu_version=int(publication_identity.builder_menu_version),
                builder_menu_row_id=option_id,
            )
            .first()
        )

    def _load_review_row_by_option(self, db, *, tenant_id: int, site_id: str, service_date: _date, meal: str, option_id: str) -> PlanningOptionReview | None:
        return self._review_row_query(
            db,
            tenant_id=tenant_id,
            site_id=site_id,
            service_date=service_date,
            meal=meal,
            option_id=option_id,
        ).first()

    def _load_decisions(self, db, review_id: int) -> list[PlanningOptionReviewDecision]:
        return (
            db.query(PlanningOptionReviewDecision)
            .filter_by(review_id=review_id)
            .order_by(
                PlanningOptionReviewDecision.destination_id.asc(),
                PlanningOptionReviewDecision.requirement_group_id.asc(),
                PlanningOptionReviewDecision.id.asc(),
            )
            .all()
        )

    def _build_basis(self, *, tenant_id: int, site_id: str, service_date: _date, meal: str, scope: _ResolvedOptionScope) -> PlanningOptionReviewBasis | None:
        if scope.publication_identity is None or scope.option_id is None:
            return None
        payload = build_option_review_basis_payload(
            tenant_id=tenant_id,
            site_id=site_id,
            service_date=service_date,
            meal=meal,
            publication_identity=scope.publication_identity,
            option_id=scope.option_id,
            assigned_destinations=scope.assigned_destinations,
            relevant_groups=scope.relevant_groups,
        )
        return PlanningOptionReviewBasis(payload=payload, review_basis_hash=compute_option_review_basis_hash(payload))

    def _count_decisions(self, decisions: Iterable[PlanningOptionReviewDecisionState]) -> tuple[int, int]:
        no_adaptation_count = 0
        adaptation_count = 0
        for decision in decisions:
            if decision.decision == NO_ADAPTATION_REQUIRED:
                no_adaptation_count += 1
            elif decision.decision == ADAPTATION_REQUIRED:
                adaptation_count += 1
        return no_adaptation_count, adaptation_count

    def _state_from_row(
        self,
        *,
        review: PlanningOptionReview | None,
        decision_rows: Iterable[PlanningOptionReviewDecision],
        current_basis_hash: str | None,
        current_relevant_group_count: int,
    ) -> PlanningOptionReviewState:
        decisions = tuple(
            PlanningOptionReviewDecisionState(
                destination_id=str(row.destination_id),
                requirement_group_id=str(row.requirement_group_id),
                decision=str(row.decision),
            )
            for row in decision_rows
        )
        no_adaptation_count, adaptation_count = self._count_decisions(decisions)
        review_is_stale = review is not None and (current_basis_hash is None or str(review.review_basis_hash) != current_basis_hash)
        if review is None or review_is_stale:
            review_state = REVIEW_STATE_UNREVIEWED
        elif adaptation_count > 0:
            review_state = REVIEW_STATE_WITH_DEVIATIONS
        else:
            review_state = REVIEW_STATE_NO_DEVIATIONS
        return PlanningOptionReviewState(
            review_state=review_state,
            review_is_stale=bool(review_is_stale),
            review_id=int(review.id) if review is not None else None,
            review_basis_hash=str(review.review_basis_hash) if review is not None else None,
            current_basis_hash=current_basis_hash,
            reviewed_by_user_id=int(review.reviewed_by_user_id) if review is not None else None,
            reviewed_at=review.reviewed_at if review is not None else None,
            completed_at=review.completed_at if review is not None else None,
            relevant_group_count=int(current_relevant_group_count),
            decision_count=len(decisions),
            no_adaptation_count=no_adaptation_count,
            adaptation_count=adaptation_count,
            decisions=decisions,
        )

    def _load_state(
        self,
        *,
        db,
        tenant_id: int,
        site_id: str,
        service_date: _date,
        meal: str,
        option_id: str,
        scope: _ResolvedOptionScope,
        basis: PlanningOptionReviewBasis | None,
    ) -> PlanningOptionReviewState:
        review = None
        if scope.publication_identity is not None and scope.option_id is not None:
            review = self._load_review_row_exact(
                db,
                tenant_id=tenant_id,
                site_id=site_id,
                service_date=service_date,
                meal=meal,
                publication_identity=scope.publication_identity,
                option_id=scope.option_id,
            )
        if review is None:
            review = self._load_review_row_by_option(
                db,
                tenant_id=tenant_id,
                site_id=site_id,
                service_date=service_date,
                meal=meal,
                option_id=option_id,
            )
        decision_rows = self._load_decisions(db, int(review.id)) if review is not None else []
        current_basis_hash = basis.review_basis_hash if basis is not None and scope.option_id is not None else None
        return self._state_from_row(
            review=review,
            decision_rows=decision_rows,
            current_basis_hash=current_basis_hash,
            current_relevant_group_count=len(scope.relevant_groups),
        )

    def save_option_review(
        self,
        *,
        tenant_id,
        site_id,
        service_date,
        meal,
        option_id,
        decisions: Iterable[object],
        reviewed_by_user_id,
    ) -> PlanningOptionReviewState:
        normalized_tenant_id = _normalize_tenant_id(tenant_id)
        normalized_site_id = _normalize_site_id(site_id)
        normalized_service_date = _normalize_service_date(service_date)
        normalized_meal = _normalize_meal(meal)
        normalized_option_id = _normalize_option_id(option_id)
        normalized_user_id = _normalize_user_id(reviewed_by_user_id)
        site_tenant_id = get_site_tenant(normalized_site_id)
        if site_tenant_id is None or int(site_tenant_id) != normalized_tenant_id:
            raise PlanningOptionReviewError("site_tenant_mismatch")

        context = self._load_context(
            tenant_id=normalized_tenant_id,
            site_id=normalized_site_id,
            service_date=normalized_service_date,
            meal=normalized_meal,
        )
        scope = self._resolve_scope(context=context, option_id=normalized_option_id)
        if scope.publication_identity is None or scope.option_id is None:
            raise PlanningOptionReviewError("option_not_published")
        basis = self._build_basis(
            tenant_id=normalized_tenant_id,
            site_id=normalized_site_id,
            service_date=normalized_service_date,
            meal=normalized_meal,
            scope=scope,
        )
        assert basis is not None

        current_relevant_keys = {
            (str(group.destination_id), str(group.requirement_group_id)): group for group in scope.relevant_groups
        }
        normalized_decisions: list[PlanningOptionReviewDecisionInput] = []
        seen_keys: set[tuple[str, str]] = set()
        for raw_decision in decisions:
            decision = _normalize_decision_item(raw_decision)
            if not decision.destination_id or not decision.requirement_group_id:
                raise PlanningOptionReviewError("decision_identity_missing")
            key = (decision.destination_id, decision.requirement_group_id)
            if key in seen_keys:
                raise PlanningOptionReviewError("duplicate_decision")
            if key not in current_relevant_keys:
                raise PlanningOptionReviewError("irrelevant_decision")
            seen_keys.add(key)
            normalized_decisions.append(decision)

        missing_keys = sorted(set(current_relevant_keys) - seen_keys)
        if missing_keys:
            raise PlanningOptionReviewError("missing_decision")

        db = get_session()
        try:
            self._ensure_tables(db)
            review = self._load_review_row_exact(
                db,
                tenant_id=normalized_tenant_id,
                site_id=normalized_site_id,
                service_date=normalized_service_date,
                meal=normalized_meal,
                publication_identity=scope.publication_identity,
                option_id=scope.option_id,
            )
            now = _datetime.now(UTC)
            if review is None:
                review = PlanningOptionReview(
                    tenant_id=normalized_tenant_id,
                    site_id=normalized_site_id,
                    service_date=normalized_service_date,
                    meal=normalized_meal,
                    builder_menu_id=str(scope.publication_identity.builder_menu_id),
                    builder_menu_version=int(scope.publication_identity.builder_menu_version),
                    builder_menu_row_id=scope.option_id,
                    review_basis_version=_BASIS_VERSION,
                    review_basis_hash=basis.review_basis_hash,
                    reviewed_by_user_id=normalized_user_id,
                    reviewed_at=now,
                    completed_at=now,
                    created_at=now,
                    updated_at=now,
                )
                db.add(review)
                db.flush()
            else:
                review.builder_menu_id = str(scope.publication_identity.builder_menu_id)
                review.builder_menu_version = int(scope.publication_identity.builder_menu_version)
                review.builder_menu_row_id = scope.option_id
                review.review_basis_version = _BASIS_VERSION
                review.review_basis_hash = basis.review_basis_hash
                review.reviewed_by_user_id = normalized_user_id
                review.reviewed_at = now
                review.completed_at = now
                review.updated_at = now
                db.flush()

            db.query(PlanningOptionReviewDecision).filter_by(review_id=int(review.id)).delete(synchronize_session=False)
            for decision in normalized_decisions:
                db.add(
                    PlanningOptionReviewDecision(
                        review_id=int(review.id),
                        tenant_id=normalized_tenant_id,
                        destination_id=decision.destination_id,
                        requirement_group_id=decision.requirement_group_id,
                        decision=decision.decision,
                        created_at=now,
                        updated_at=now,
                    )
                )
            db.commit()
            return self.get_option_review_state(
                tenant_id=normalized_tenant_id,
                site_id=normalized_site_id,
                service_date=normalized_service_date,
                meal=normalized_meal,
                option_id=normalized_option_id,
            )
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def get_option_review_state(
        self,
        *,
        tenant_id,
        site_id,
        service_date,
        meal,
        option_id,
    ) -> PlanningOptionReviewState:
        normalized_tenant_id = _normalize_tenant_id(tenant_id)
        normalized_site_id = _normalize_site_id(site_id)
        normalized_service_date = _normalize_service_date(service_date)
        normalized_meal = _normalize_meal(meal)
        normalized_option_id = _normalize_option_id(option_id)
        site_tenant_id = get_site_tenant(normalized_site_id)
        if site_tenant_id is None or int(site_tenant_id) != normalized_tenant_id:
            raise PlanningOptionReviewError("site_tenant_mismatch")

        context = self._load_context(
            tenant_id=normalized_tenant_id,
            site_id=normalized_site_id,
            service_date=normalized_service_date,
            meal=normalized_meal,
        )
        scope = self._resolve_scope(context=context, option_id=normalized_option_id)
        basis = self._build_basis(
            tenant_id=normalized_tenant_id,
            site_id=normalized_site_id,
            service_date=normalized_service_date,
            meal=normalized_meal,
            scope=scope,
        )

        db = get_session()
        try:
            self._ensure_tables(db)
            return self._load_state(
                db=db,
                tenant_id=normalized_tenant_id,
                site_id=normalized_site_id,
                service_date=normalized_service_date,
                meal=normalized_meal,
                option_id=normalized_option_id,
                scope=scope,
                basis=basis,
            )
        finally:
            db.close()


__all__ = [
    "ADAPTATION_REQUIRED",
    "NO_ADAPTATION_REQUIRED",
    "PlanningOptionReviewBasis",
    "PlanningOptionReviewDecisionInput",
    "PlanningOptionReviewDecisionState",
    "PlanningOptionReviewError",
    "PlanningOptionReviewService",
    "PlanningOptionReviewState",
    "REVIEW_STATE_NO_DEVIATIONS",
    "REVIEW_STATE_UNREVIEWED",
    "REVIEW_STATE_WITH_DEVIATIONS",
    "build_option_review_basis_payload",
    "compute_option_review_basis_hash",
]
