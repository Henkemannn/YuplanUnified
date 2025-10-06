from __future__ import annotations

from typing import Any, Literal, TypedDict

__all__ = [
    "RawRow",
    "NormalizedRow",
    "ErrorDetail",
    "ImportValidationError",
    "UnsupportedFormatError",
]


# Dynamic raw row mapping (arbitrary header -> raw string value)
RawRow = dict[str, str]


class NormalizedRow(TypedDict):
    """Normalized, validated row ready for persistence.

    This structure should be stable for downstream usage.
    Add new optional keys carefully.
    """

    title: str
    description: str
    priority: int


class ErrorDetail(TypedDict):
    row_index: int
    column: str | None
    code: Literal[
        "missing_column",
        "empty_value",
        "invalid_int",
        "unexpected_extra_column",
    ]
    message: str


class ImportValidationError(Exception):
    """Raised when one or more validation errors occur.

    Carries a list of structured `ErrorDetail` dictionaries for reporting.
    """

    def __init__(self, errors: list[ErrorDetail]):
        super().__init__("Import validation failed")
        self.errors = errors

    def to_dict(self) -> dict[str, Any]:  # pragma: no cover - convenience
        return {"errors": self.errors}


class UnsupportedFormatError(Exception):
    """Raised when attempting to import a format we do not support (yet)."""
