"""Import API (Pocket 10)

Exposes CSV / DOCX / XLSX importers with unified response envelope.
All endpoints require editor|admin role.
Optional rate limiting via feature flag `rate_limit_import`.
"""

from __future__ import annotations

from io import BytesIO
from typing import Literal, TypedDict, cast

from flask import Blueprint, jsonify, request, session, current_app

from .app_authz import require_roles, AuthzError
from .rate_limit import RateLimitExceeded, allow, rate_limited_response
from .importers.csv_importer import parse_csv
from .importers.validate import validate_and_normalize, ImportValidationError

try:  # pragma: no cover - optional dependency
    from .importers.docx_table_importer import parse_docx  # type: ignore
except Exception:  # pragma: no cover
    parse_docx = None  # type: ignore

try:  # pragma: no cover - optional dependency
    from .importers.xlsx_importer import parse_xlsx  # type: ignore
except Exception:  # pragma: no cover
    parse_xlsx = None  # type: ignore

bp = Blueprint("import_api", __name__, url_prefix="/import")

class ImportRow(TypedDict, total=False):
    title: str
    description: str
    priority: int

class ImportOkResponse(TypedDict):
    ok: Literal[True]
    rows: list[ImportRow]
    meta: dict[str, int]

class ImportErrorResponse(TypedDict, total=False):
    ok: Literal[False]
    error: Literal["invalid", "unsupported"]
    message: str

ALLOWED_ROLES = ("editor", "admin")
MAX_FILE_BYTES = 5 * 1024 * 1024  # 5MB guard


def _tenant_id() -> int:
    tid = session.get("tenant_id")
    if tid is None:
        raise AuthzError("forbidden", required="admin")
    return int(tid)


def _rate_limited(kind: str):
    """Apply optional rate limiting if enabled via FEATURE_FLAGS config.

    Tests pass FEATURE_FLAGS={"rate_limit_import": True} when they want the
    limiter enforced. We intentionally decouple from the feature registry for
    now (flag not seeded) to avoid mutating registry state during tests.
    """
    tid = _tenant_id()
    flags = current_app.config.get("FEATURE_FLAGS") or {}
    try:
        enabled = bool(flags.get("rate_limit_import"))  # type: ignore[arg-type]
    except Exception:  # pragma: no cover - defensive
        enabled = False
    if enabled:
        try:
            allow(tid, session.get("user_id"), f"import_{kind}", 60, testing=current_app.config.get("TESTING", False))
        except RateLimitExceeded:
            return rate_limited_response()
    return None


def _load_file_bytes() -> bytes:
    if "file" not in request.files:
        raise ImportValidationError([{"row_index": -1, "column": None, "code": "missing_file", "message": "file field required"}])  # type: ignore[list-item]
    storage = request.files["file"]
    raw = storage.read()
    if len(raw) > MAX_FILE_BYTES:
        raise ImportValidationError([{"row_index": -1, "column": None, "code": "too_large", "message": "file exceeds 5MB"}])  # type: ignore[list-item]
    return raw


def _normalize(rows):
    normalized = validate_and_normalize(rows)
    return normalized  # list[ImportRow]


def _ok(rows) -> ImportOkResponse:  # type: ignore[no-untyped-def]
    rows_list = cast(list[ImportRow], rows)
    return {"ok": True, "rows": rows_list, "meta": {"count": len(rows_list)}}


@bp.post("/csv")
@require_roles(*ALLOWED_ROLES)
def import_csv():  # type: ignore[return-value]
    rl = _rate_limited("csv")
    if rl is not None:
        return rl
    try:
        data = _load_file_bytes()
        # Lightweight MIME / extension gate: reject clearly wrong types (future: sniff magic bytes)
        storage = request.files.get("file") if "file" in request.files else None
        filename = getattr(storage, "filename", "")
        lowered = (filename or "").lower()
        ctype = getattr(storage, "mimetype", None)
        if not (lowered.endswith(".csv") or (ctype and ctype in ("text/csv", "application/vnd.ms-excel", "application/octet-stream"))):
            return jsonify({"ok": False, "error": "unsupported", "message": "Only CSV upload supported at this endpoint"}), 415
        parsed = parse_csv(data.decode("utf-8", errors="replace"))
        rows = _normalize(parsed.rows)
        return jsonify(_ok(rows))
    except ImportValidationError as e:
        return jsonify({"ok": False, "error": "invalid", "message": str(e)}), 400


@bp.post("/docx")
@require_roles(*ALLOWED_ROLES)
def import_docx():  # type: ignore[return-value]
    if parse_docx is None:
        return jsonify({"ok": False, "error": "unsupported", "message": "docx import not available"}), 415
    rl = _rate_limited("docx")
    if rl is not None:
        return rl
    try:
        data = _load_file_bytes()
        # parse_docx expects raw bytes (it wraps internally)
        parsed = parse_docx(data)  # type: ignore[misc]
        rows = _normalize(parsed.rows)
        return jsonify(_ok(rows))
    except ImportValidationError as e:
        return jsonify({"ok": False, "error": "invalid", "message": str(e)}), 400


@bp.post("/xlsx")
@require_roles(*ALLOWED_ROLES)
def import_xlsx():  # type: ignore[return-value]
    if parse_xlsx is None:
        return jsonify({"ok": False, "error": "unsupported", "message": "xlsx import not available"}), 415
    rl = _rate_limited("xlsx")
    if rl is not None:
        return rl
    try:
        data = _load_file_bytes()
        parsed = parse_xlsx(data)  # type: ignore[misc]
        rows = _normalize(parsed.rows)
        return jsonify(_ok(rows))
    except ImportValidationError as e:
        return jsonify({"ok": False, "error": "invalid", "message": str(e)}), 400

__all__ = ["bp"]

# --- Menu Import (legacy dry-run support for tests) ---
try:  # pragma: no cover - optional existing importer
    from .importers.menu_importer import MenuImporter  # type: ignore
    _importer = MenuImporter()  # type: ignore
except Exception:  # pragma: no cover
    _importer = None  # type: ignore

@bp.post("/menu")
@require_roles(*ALLOWED_ROLES)
def import_menu():  # type: ignore[return-value]
    """Legacy menu import endpoint with ?dry_run=1 support.

    Tests monkeypatch `core.import_api._importer` to a dummy importer exposing
    `.parse(data, filename, mime)` returning an object with `.weeks`.
    Each week holds `items` iterable containing attributes: day, meal,
    variant_type, dish_name.
    """
    imp = globals().get("_importer")
    if imp is None:
        return jsonify({"ok": False, "error": "unsupported", "message": "menu importer not available"}), 415
    dry_run = request.args.get("dry_run") == "1"
    try:
        data = _load_file_bytes()
    except ImportValidationError as e:
        return jsonify({"ok": False, "error": "invalid", "message": str(e)}), 400
    storage = request.files.get("file") if "file" in request.files else None
    filename = getattr(storage, "filename", "menu.bin")
    mime = getattr(storage, "mimetype", "application/octet-stream")
    try:
        result = imp.parse(data, filename, mime)  # type: ignore[attr-defined]
    except Exception as ex:  # pragma: no cover - broad safety
        return jsonify({"ok": False, "error": "invalid", "message": str(ex)}), 400
    # Build diff list (dry-run semantics only; no persistence implemented)
    diff: list[dict[str, object]] = []
    for wk in getattr(result, "weeks", []):  # type: ignore[iteration-over-annotated]
        for it in getattr(wk, "items", []):
            diff.append({
                "day": getattr(it, "day", None),
                "meal": getattr(it, "meal", None),
                "variant_type": getattr(it, "variant_type", None),
                "dish_name": getattr(it, "dish_name", None),
                "variant_action": "create",  # placeholder (no existing lookup yet)
            })
    # Map diff entries to generic ImportRow-like minimal rows (best-effort)
    rows = [
        {
            "title": (d.get("dish_name") or "")[:120],
            "description": f"{d.get('day')} {d.get('meal')} {d.get('variant_type')}",
            "priority": 0,
        }
        for d in diff
    ]
    return jsonify({
        "ok": True,
        "dry_run": bool(dry_run),  # legacy field expected by older test
        "rows": rows,
        "meta": {"count": len(rows), "dry_run": bool(dry_run)},
        "diff": diff,
    })
