from __future__ import annotations

from collections.abc import Sequence

from .base_types import (
    ErrorDetail,
    ImportValidationError,
    NormalizedRow,
    RawRow,
)

REQUIRED_COLUMNS: Sequence[str] = ("title", "description", "priority")

__all__ = ["validate_and_normalize", "REQUIRED_COLUMNS"]


def validate_and_normalize(rows: list[RawRow]) -> list[NormalizedRow]:
    """Validate raw rows and produce normalized rows.

    Validation rules:
    - All REQUIRED_COLUMNS must be present in each row (missing -> error).
    - Empty required values -> error.
    - priority must be an integer (invalid -> error).
    - Extra columns (beyond REQUIRED_COLUMNS) produce an error but do not block processing.

    Returns list of successfully normalized rows. If any validation errors for required
    fields or type conversions occur, an ImportValidationError is raised (with all errors).
    Extra column errors are included but are non-fatal (we still include row if required
    fields valid). For now we treat all errors as fatal to simplify feedback loop.
    """

    errors: list[ErrorDetail] = []
    normalized: list[NormalizedRow] = []

    for idx, row in enumerate(rows):
        row_errors: list[ErrorDetail] = []
        # Missing / empty checks
        missing_columns = [c for c in REQUIRED_COLUMNS if c not in row]
        for col in missing_columns:
            row_errors.append(
                ErrorDetail(
                    row_index=idx,
                    column=col,
                    code="missing_column",
                    message=f"Missing required column '{col}'",
                )
            )
        # Skip deeper validation if fundamental columns missing
        if missing_columns:
            errors.extend(row_errors)
            continue

        title = str(row.get("title", "")).strip()
        description = str(row.get("description", "")).strip()
        priority_raw = str(row.get("priority", "")).strip()

        if title == "":
            row_errors.append(
                ErrorDetail(
                    row_index=idx,
                    column="title",
                    code="empty_value",
                    message="Title cannot be empty",
                )
            )
        if description == "":
            row_errors.append(
                ErrorDetail(
                    row_index=idx,
                    column="description",
                    code="empty_value",
                    message="Description cannot be empty",
                )
            )

        # priority parse
        try:
            priority = int(priority_raw)
        except ValueError:
            row_errors.append(
                ErrorDetail(
                    row_index=idx,
                    column="priority",
                    code="invalid_int",
                    message=f"Priority must be an integer, got '{priority_raw}'",
                )
            )
            priority = 0  # placeholder so variable defined

        # Extra columns
        extra_cols = [c for c in row if c not in REQUIRED_COLUMNS]
        for col in extra_cols:
            row_errors.append(
                ErrorDetail(
                    row_index=idx,
                    column=col,
                    code="unexpected_extra_column",
                    message=f"Unexpected column '{col}' ignored",
                )
            )

        if row_errors:
            errors.extend(row_errors)
            # Decision: fail-fast whole import if any row has errors.
            continue

        normalized.append(
            NormalizedRow(
                title=title,
                description=description,
                priority=priority,
            )
        )

    if errors:
        raise ImportValidationError(errors)

    return normalized
