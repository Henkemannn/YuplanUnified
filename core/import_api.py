"""Import API (Pocket 10)

Exposes CSV / DOCX / XLSX importers with unified response envelope.
All endpoints require editor|admin role.
Optional rate limiting via feature flag `rate_limit_import`.
"""

from __future__ import annotations

from typing import Any, Literal, cast

from flask import Blueprint, current_app, jsonify, request, session
from werkzeug.datastructures import FileStorage

from .api_types import ImportErrorResponse, ImportOkResponse
from .app_authz import AuthzError, require_roles
from .importers.csv_importer import parse_csv
from .importers.validate import ImportValidationError, validate_and_normalize
from .rate_limit import RateLimitExceeded, allow, rate_limited_response
from .roles import CanonicalRole

try:  # pragma: no cover - optional dependency
    from .importers.docx_table_importer import parse_docx  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    parse_docx = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency
    from .importers.xlsx_importer import parse_xlsx  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    parse_xlsx = None  # type: ignore[assignment]

bp = Blueprint("import_api", __name__, url_prefix="/import")

ImportRow = dict[str, str]

# Narrow to canonical literals accepted by require_roles (order matters for error message)
ALLOWED_ROLES: tuple[CanonicalRole, CanonicalRole] = ("editor", "admin")
MAX_FILE_BYTES = 5 * 1024 * 1024  # 5MB guard


def _tenant_id() -> int:
    tid = session.get("tenant_id")
    if tid is None:
        # Use canonical error mapping; required role 'admin' chosen to surface expectation.
        raise AuthzError("forbidden", required="admin")
    return int(tid)


def _rate_limited(kind: str) -> Any | None:
    """Apply optional rate limiting if feature flag enabled.

    Returns Flask response object (Any) if limited, else None.
    """
    tid = _tenant_id()
    flags = current_app.config.get("FEATURE_FLAGS") or {}
    enabled = bool(flags.get("rate_limit_import")) if isinstance(flags, dict) else False
    if enabled:
        try:
            allow(
                tid,
                cast(int | None, session.get("user_id")),
                f"import_{kind}",
                60,
                testing=current_app.config.get("TESTING", False),
            )
        except RateLimitExceeded:
            # Provide minimal retry hint
            return rate_limited_response(1)
    return None


def _file_from_request() -> FileStorage | None:
    fs = request.files.get("file")
    return cast(FileStorage | None, fs)


def _file_to_bytes(fs: FileStorage) -> bytes:
    raw = fs.read()
    if not raw:
        # Empty upload considered invalid input
        raise ImportValidationError([])
    if len(raw) > MAX_FILE_BYTES:
        raise ImportValidationError([])
    return raw


def _normalize(rows: list[dict[str, str]]) -> list[ImportRow]:
    # Already in RawRow shape (dict[str,str]) from importer layer
    normalized_internal = validate_and_normalize(rows)
    return [cast(ImportRow, nr) for nr in normalized_internal]


def _ok(
    rows: list[dict[str, str]],
    *,
    fmt: Literal["csv", "docx", "xlsx", "menu"],
    dry_run: bool = False,
) -> ImportOkResponse:
    meta: dict[str, Any] = {"count": len(rows), "format": fmt}
    if dry_run:
        meta["dry_run"] = True
    resp: ImportOkResponse = {
        "ok": True,
        "rows": rows,
        "meta": cast(Any, meta),
    }  # meta conforms to ImportMeta
    if dry_run:
        resp["dry_run"] = True  # legacy alias
    return resp


def _err(code: str, msg: str, status: int):
    payload: ImportErrorResponse = {"ok": False, "error": code, "message": msg}
    resp = jsonify(payload)
    return resp, status


def _is_csv(filename: str, mimetype: str | None) -> bool:
    low = filename.lower()
    return low.endswith(".csv") or (
        mimetype in {"text/csv", "application/vnd.ms-excel", "application/octet-stream"}
    )


def _is_docx(filename: str, mimetype: str | None) -> bool:
    low = filename.lower()
    return (
        low.endswith(".docx")
        or mimetype == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


def _is_xlsx(filename: str, mimetype: str | None) -> bool:
    low = filename.lower()
    return low.endswith(".xlsx") or mimetype in {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    }


@bp.post("/csv")
@require_roles(*ALLOWED_ROLES)
def import_csv():  # Flask view
    rl = _rate_limited("csv")
    if rl is not None:
        return rl
    storage = _file_from_request()
    if storage is None:
        return _err("invalid", "file field required", 400)
    if not _is_csv(storage.filename or "", storage.mimetype):
        return _err("unsupported", "Only CSV upload supported", 415)
    try:
        data = _file_to_bytes(storage)
        parsed = parse_csv(data.decode("utf-8", errors="replace"))
        rows = _normalize(cast(list[dict[str, str]], parsed.rows))
        from flask import jsonify

        return jsonify(_ok(rows, fmt="csv"))
    except ImportValidationError:
        return _err("invalid", "Import validation failed", 400)


@bp.post("/docx")
@require_roles(*ALLOWED_ROLES)
def import_docx():  # dynamic Response
    if parse_docx is None:
        return _err("unsupported", "docx import not available", 415)
    rl = _rate_limited("docx")
    if rl is not None:
        return rl
    storage = _file_from_request()
    if storage is None:
        return _err("invalid", "file field required", 400)
    if not _is_docx(storage.filename or "", storage.mimetype):
        return _err("unsupported", "Only DOCX upload supported", 415)
    try:
        data = _file_to_bytes(storage)
        parsed = parse_docx(data)  # type: ignore[call-arg]
        rows = _normalize(cast(list[dict[str, str]], parsed.rows))
        from flask import jsonify

        return jsonify(_ok(rows, fmt="docx"))
    except ImportValidationError:
        return _err("invalid", "Import validation failed", 400)


@bp.post("/xlsx")
@require_roles(*ALLOWED_ROLES)
def import_xlsx():  # dynamic Response
    if parse_xlsx is None:
        return _err("unsupported", "xlsx import not available", 415)
    rl = _rate_limited("xlsx")
    if rl is not None:
        return rl
    storage = _file_from_request()
    if storage is None:
        return _err("invalid", "file field required", 400)
    if not _is_xlsx(storage.filename or "", storage.mimetype):
        return _err("unsupported", "Only XLSX upload supported", 415)
    try:
        data = _file_to_bytes(storage)
        parsed = parse_xlsx(data)  # type: ignore[call-arg]
        rows = _normalize(cast(list[dict[str, str]], parsed.rows))
        from flask import jsonify

        return jsonify(_ok(rows, fmt="xlsx"))
    except ImportValidationError:
        return _err("invalid", "Import validation failed", 400)


__all__ = ["bp"]

# --- Menu Import (legacy dry-run support for tests) ---
try:  # pragma: no cover - optional existing importer
    from .importers.menu_importer import MenuImporter  # type: ignore[import-not-found]

    _importer: Any | None = MenuImporter()  # type: ignore[misc]
except Exception:  # pragma: no cover
    _importer = None


@bp.post("/menu")
@require_roles(*ALLOWED_ROLES)
def import_menu():  # dynamic Response
    """Legacy menu import endpoint with ?dry_run=1 support.

    Tests monkeypatch `core.import_api._importer` to a dummy importer exposing
    `.parse(data, filename, mime)` returning an object with `.weeks`.
    Each week holds `items` iterable containing attributes: day, meal,
    variant_type, dish_name.
    """
    imp = globals().get("_importer")
    if imp is None:
        return _err("unsupported", "menu importer not available", 415)
    dry_run = request.args.get("dry_run") == "1"
    try:
        # menu importer expects bytes; reuse existing file loader path
        fs = _file_from_request()
        if fs is None:
            return _err("invalid", "file field required", 400)
        data = _file_to_bytes(fs)
    except ImportValidationError:
        return _err("invalid", "Import validation failed", 400)
    storage = request.files.get("file") if "file" in request.files else None
    filename = getattr(storage, "filename", "menu.bin")
    mime = getattr(storage, "mimetype", "application/octet-stream")
    try:
        result = imp.parse(data, filename, mime)  # type: ignore[attr-defined]
    except Exception as ex:  # pragma: no cover - broad safety
        return _err("invalid", str(ex), 400)
    # Build diff list (dry-run semantics only; no persistence implemented)
    diff: list[dict[str, object]] = []
    for wk in getattr(result, "weeks", []):  # type: ignore[iteration-over-annotated]
        for it in getattr(wk, "items", []):
            diff.append(
                {
                    "day": getattr(it, "day", None),
                    "meal": getattr(it, "meal", None),
                    "variant_type": getattr(it, "variant_type", None),
                    "dish_name": getattr(it, "dish_name", None),
                    "variant_action": "create",  # placeholder (no existing lookup yet)
                }
            )
    # Map diff entries to generic ImportRow-like minimal rows (best-effort)
    rows: list[dict[str, str]] = []
    for d in diff:
        dish = str(d.get("dish_name") or "")
        day = d.get("day")
        meal = d.get("meal")
        variant_type = d.get("variant_type")
        rows.append(
            {
                "title": dish[:120],
                "description": f"{day} {meal} {variant_type}",
                "priority": "0",
            }
        )
    ok_payload = _ok(rows, fmt="menu", dry_run=dry_run)
    ok_payload["diff"] = diff  # type: ignore[index]
    return jsonify(ok_payload)
