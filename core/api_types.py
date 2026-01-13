"""Central API response/request type contracts (Pocket 4 groundwork).

Design principles:
 - Unified ok/error model via Literal True/False.
 - No Any: explicit TypedDicts & NewType wrappers for identifiers.
 - Prefer NotRequired over Optional[...]=None when field may be omitted.
 - Reuse service-layer row types via forward references to avoid heavy imports.

Runtime behavior of endpoints SHOULD NOT depend on these definitions; they
exist for static analysis (mypy strict pocket rollout).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, NewType, NotRequired, TypedDict

if TYPE_CHECKING:  # import only for type checking to resolve forward refs
    from .service_metrics_service import MetricRow, SummaryDayRow  # pragma: no cover


# --- Identifier NewTypes ---
TenantId = NewType("TenantId", int)
FeatureName = NewType("FeatureName", str)
UnitId = NewType("UnitId", int)
DietTypeId = NewType("DietTypeId", int)
AssignmentId = NewType("AssignmentId", int)
TaskId = NewType("TaskId", int)


## Envelopes
class OkBase(TypedDict):
    ok: Literal[True]


class ErrorResponse(TypedDict, total=False):
    ok: Literal[False]
    error: str
    message: NotRequired[str]


# --- Tasks ---
TaskStatus = Literal["todo", "doing", "blocked", "done", "cancelled"]


class TaskSummary(TypedDict, total=False):
    id: TaskId
    title: str
    status: TaskStatus
    owner: TenantId | int
    assignee: NotRequired[str]
    due: NotRequired[str]


class TaskListResponse(OkBase):
    tasks: list[TaskSummary]


class TaskCreateRequest(TypedDict, total=False):
    title: str
    assignee: NotRequired[str]
    due: NotRequired[str]
    status: NotRequired[TaskStatus]
    done: NotRequired[bool]


class TaskCreateResponse(OkBase, total=False):
    task_id: TaskId
    task: NotRequired[dict]
    location: NotRequired[str]


class TaskUpdateRequest(TypedDict, total=False):
    status: NotRequired[TaskStatus]
    assignee: NotRequired[str]
    title: NotRequired[str]
    due: NotRequired[str]


class TaskUpdateResponse(OkBase, total=False):
    updated: bool
    task: NotRequired[dict]


# --- Admin ---
class TenantSummary(TypedDict, total=False):
    id: TenantId
    name: str
    active: bool
    kind: NotRequired[str | None]
    description: NotRequired[str | None]
    features: list[str]


class TenantListResponse(OkBase):
    tenants: list[TenantSummary]


class TenantCreateResponse(OkBase):
    tenant_id: TenantId


class FeatureToggleResponse(OkBase, total=False):
    tenant_id: TenantId
    feature: str
    enabled: bool
    features: NotRequired[list[str]]


# --- Diet ---
class DietType(TypedDict):
    id: DietTypeId
    name: str
    default_select: bool


class DietTypeListResponse(OkBase):
    diet_types: list[DietType]


class DietTypeCreateResponse(OkBase):
    diet_type_id: DietTypeId


class GenericOk(OkBase):
    pass


class UnitSummary(TypedDict):
    id: UnitId
    name: str


class UnitListResponse(OkBase):
    units: list[UnitSummary]


class Assignment(TypedDict):
    id: AssignmentId
    unit_id: UnitId
    diet_type_id: DietTypeId
    count: int


class AssignmentListResponse(OkBase):
    unit_id: UnitId
    assignments: list[Assignment]


class AssignmentCreateResponse(OkBase):
    assignment_id: AssignmentId


# --- Service Metrics (referencing service-layer row types) ---
class MetricsQueryRowsResponse(OkBase):
    rows: list[MetricRow]  # forward ref; defined in service_metrics_service


class MetricsSummaryDayResponse(OkBase):
    rows: list[SummaryDayRow]  # forward ref


class IngestResponse(OkBase, total=False):
    ingested: NotRequired[int]
    skipped: NotRequired[int]
    details: NotRequired[list]


# --- Limits Inspection ---
class LimitView(TypedDict, total=False):
    name: str
    quota: int
    per_seconds: int
    source: Literal["tenant", "default", "fallback"]
    tenant_id: NotRequired[int]


class LimitUpsertRequest(TypedDict, total=False):
    tenant_id: int
    name: str
    quota: int
    per_seconds: int


class LimitDeleteRequest(TypedDict, total=False):
    tenant_id: int
    name: str


class LimitMutationResponse(OkBase, total=False):
    item: NotRequired[LimitView]
    updated: NotRequired[bool]
    removed: NotRequired[bool]


# --- Service Recommendation ---
class RecommendationResponse(TypedDict, total=False):
    category: str
    guest_count: int
    recommended_g_per_guest: float | int
    total_gram: float | int
    total_protein: float | None
    source: str
    sample_size: int
    baseline_used: bool
    history_mean_raw: float | None
    history_mean_used: float | None


# --- Import API ---
class ImportMeta(TypedDict, total=False):
    count: int
    dry_run: NotRequired[bool]
    format: NotRequired[Literal["csv", "docx", "xlsx", "menu"]]


class ImportOkResponse(OkBase, total=False):
    rows: list[dict[str, str]]
    meta: ImportMeta
    # Legacy alias (sunset TBD)
    dry_run: NotRequired[bool]
    # Menu import dry-run diff entries (free-form objects)
    diff: NotRequired[list[dict[str, object]]]


class ImportErrorResponse(TypedDict, total=False):
    ok: Literal[False]
    error: str
    message: NotRequired[str]


__all__ = [
    # NewTypes
    "TenantId",
    "FeatureName",
    "UnitId",
    "DietTypeId",
    "AssignmentId",
    "TaskId",
    # Envelopes / errors
    "OkBase",
    "ErrorResponse",
    # Admin
    "TenantSummary",
    "TenantListResponse",
    "TenantCreateResponse",
    "FeatureToggleResponse",
    # Diet
    "DietType",
    "DietTypeListResponse",
    "DietTypeCreateResponse",
    "GenericOk",
    "UnitSummary",
    "UnitListResponse",
    "Assignment",
    "AssignmentListResponse",
    "AssignmentCreateResponse",
    # Tasks
    "TaskStatus",
    "TaskSummary",
    "TaskListResponse",
    "TaskCreateRequest",
    "TaskCreateResponse",
    "TaskUpdateRequest",
    "TaskUpdateResponse",
    # Metrics
    "MetricsQueryRowsResponse",
    "MetricsSummaryDayResponse",
    "IngestResponse",
    # Recommendation
    "RecommendationResponse",
    "LimitView",
    "LimitUpsertRequest",
    "LimitDeleteRequest",
    "LimitMutationResponse",
    # Import
    "ImportMeta",
    "ImportOkResponse",
    "ImportErrorResponse",
]
