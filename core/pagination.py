from __future__ import annotations

from collections.abc import Sequence
from typing import Generic, Literal, TypeVar

from typing_extensions import TypedDict

T = TypeVar("T")

__all__ = [
    "PageRequest",
    "PageMeta",
    "PageResponse",
    "parse_page_params",
    "paginate_sequence",
    "PaginationError",
]

# ---- Contracts -----------------------------------------------------------------

class PageRequest(TypedDict):
    page: int  # 1-based
    size: int
    sort: str | None
    order: Literal["asc", "desc"]


class PageMeta(TypedDict):
    page: int
    size: int
    total: int
    pages: int


class PageResponse(TypedDict, Generic[T]):  # type: ignore[misc]
    ok: Literal[True]
    items: list[T]
    meta: PageMeta


class PaginationError(ValueError):
    """Raised when pagination query params are invalid."""


DEFAULT_PAGE = 1
DEFAULT_SIZE = 20
MAX_SIZE = 100


def parse_page_params(args: dict[str, str | None]) -> PageRequest:
    """Parse & validate pagination query params from a dict-like (e.g. request.args).

    Applies defaults and caps size to MAX_SIZE. Raises ValueError on invalid numeric input.
    """
    page_raw = args.get("page")
    size_raw = args.get("size")
    sort = args.get("sort") or None
    order_raw = (args.get("order") or "asc").lower()

    try:
        page = int(page_raw) if page_raw else DEFAULT_PAGE
    except ValueError as e:  # pragma: no cover - defensive
        raise PaginationError("invalid page parameter") from e
    try:
        size = int(size_raw) if size_raw else DEFAULT_SIZE
    except ValueError as e:  # pragma: no cover - defensive
        raise PaginationError("invalid size parameter") from e

    if page < 1:
        raise PaginationError("page must be >= 1")
    if size < 1:
        raise PaginationError("size must be >= 1")
    if size > MAX_SIZE:
        size = MAX_SIZE
    if order_raw not in ("asc", "desc"):
        order_raw = "asc"

    # Narrow type to Literal after normalization for mypy strict pocket
    from typing import cast
    order = cast(Literal["asc", "desc"], order_raw)

    return PageRequest(page=page, size=size, sort=sort, order=order)


def make_page_response(items: Sequence[T], page_req: PageRequest, total: int) -> PageResponse[T]:
    pages = (total + page_req["size"] - 1) // page_req["size"] if page_req["size"] else 0
    return PageResponse(  # type: ignore[call-arg]
        ok=True,
        items=list(items),
        meta=PageMeta(
            page=page_req["page"],
            size=page_req["size"],
            total=total,
            pages=pages,
        ),
    )


def paginate_sequence(seq: Sequence[T], page_req: PageRequest) -> PageResponse[T]:
    start = (page_req["page"] - 1) * page_req["size"]
    end = start + page_req["size"]
    sliced = seq[start:end]
    return make_page_response(sliced, page_req, len(seq))
