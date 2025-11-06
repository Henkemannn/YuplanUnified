"""Flask application factory.

Restored clean version after corruption. Provides:
 - App factory with configuration override
 - DB engine initialization
 - Feature flag registry + per-tenant overrides
 - Unified JSON error schema {error,message}
 - Blueprint registration (auth, notes, tasks, export, recommendation, docs, inline UI)
 - OpenAPI specification at /openapi.json including Error + Note/Task schemas

NOTE: This intentionally focuses on the parts required by existing tests (error schema,
error responses, paths referencing Error, Note/Task schema presence) while keeping
implementation compact.
"""

from __future__ import annotations

import logging
import time
import uuid
from importlib import import_module
from typing import Any

from flask import Flask, g, jsonify, request, session
from werkzeug.wrappers.response import Response

from .admin_api import bp as admin_api_bp
from .admin_audit_api import bp as admin_audit_bp
from .app_authz import require_roles

# Legacy JSON error handler removed in ADR-003 sweep
from .auth import bp as auth_bp, ensure_bootstrap_superuser
from .config import Config
from .db import get_session, init_engine
from .diet_api import bp as diet_api_bp
from .errors import APIError, register_error_handlers as register_domain_handlers
from .export_api import bp as export_bp
from .feature_flags import FeatureRegistry
from .import_api import bp as import_api_bp
from .inline_ui import inline_ui_bp
from .logging_setup import install_support_log_handler
from .menu_api import bp as menu_api_bp
from .metrics import set_metrics
from .metrics_logging import LoggingMetrics
from .models import TenantFeatureFlag
from .notes_api import bp as notes_bp
from .openapi_ui import bp as openapi_ui_bp
from .security import init_security
from .service_metrics_api import bp as metrics_api_bp
from .service_recommendation_api import bp as service_recommendation_bp
from .tasks_api import bp as tasks_bp
from .turnus_api import bp as turnus_api_bp
from .weekview_api import bp as weekview_api_bp
from .ui_blueprint import ui_bp

# Map of module key -> import path:attr blueprint (for dynamic registration)
MODULE_IMPORTS = {
    "municipal": "modules.municipal.views:bp",
    "offshore": "modules.offshore.views:bp",
}


def create_app(config_override: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    # --- Configuration ---
    cfg = Config.from_env()
    if config_override:
        known = {k: v for k, v in config_override.items() if hasattr(cfg, k)}
        if known:
            cfg.override(known)
        for k, v in config_override.items():  # also allow direct Flask config keys
            if k.isupper():
                app.config[k] = v
    app.config.update(cfg.to_flask_dict())
    # ProblemDetails is canonical now (ADR-003). No problem-only flag propagation.

    # --- DB setup ---
    init_engine(cfg.database_url)

    # --- Security middleware (CORS, CSRF, headers) ---
    init_security(app)

    # --- Metrics backend wiring ---
    backend = app.config.get("METRICS_BACKEND") or getattr(cfg, "metrics_backend", None) or "noop"
    if backend == "log":  # minimal logging adapter
        try:
            set_metrics(LoggingMetrics())
            app.logger.info("Metrics backend initialized: log")
        except Exception:  # pragma: no cover
            app.logger.exception(
                "Failed to initialize logging metrics backend; falling back to noop"
            )

    # --- Feature flags ---
    feature_registry = FeatureRegistry()
    # Expose for tests manipulating registry directly
    app.feature_registry = feature_registry  # type: ignore[attr-defined]

    def _load_feature_flags_logic() -> None:
        from flask import has_request_context

        if not has_request_context():
            return
        tid = getattr(g, "tenant_id", None)
        g.tenant_feature_flags = {}
        if not tid:
            return
        db = get_session()
        try:
            rows = db.query(TenantFeatureFlag).filter(TenantFeatureFlag.tenant_id == tid).all()
            g.tenant_feature_flags = {r.name: bool(r.enabled) for r in rows}
        finally:
            db.close()

    def feature_enabled(name: str) -> bool:
        override_val = getattr(g, "tenant_feature_flags", {}).get(name)
        if override_val is not None:
            return bool(override_val)
        return bool(feature_registry.enabled(name))

    @app.context_processor
    def inject_role_helpers() -> dict[str, Any]:  # pragma: no cover - template helper
        from flask import session as _session

        def has_role(*roles: str) -> bool:
            # roles may be stored as single 'role' or list 'roles'
            r_single = _session.get("role")
            r_list = _session.get("roles") or ([r_single] if r_single else [])
            return any(r in r_list for r in roles)

        return {"has_role": has_role}

    # --- Error handling ---
    # Register RFC7807 problem handlers globally (ADR-003)
    try:
        register_domain_handlers(app)
    except Exception:  # pragma: no cover
        app.logger.warning("Failed to register domain problem handlers", exc_info=True)

    # Map legacy APIError to RFC7807 responses
    from .http_errors import (
        bad_request as _problem_bad_request,
        conflict as _problem_conflict,
        forbidden as _problem_forbidden,
        internal_server_error as _problem_ise,
        not_found as _problem_not_found,
        unauthorized as _problem_unauthorized,
    )

    @app.errorhandler(APIError)
    def _handle_api_error(ex: APIError) -> Response:
        status = int(getattr(ex, "status_code", 400) or 400)
        raw_detail: Any = getattr(ex, "message", None)
        detail: str = (
            str(raw_detail)
            if raw_detail is not None
            else str(getattr(ex, "error_code", "bad_request"))
        )
        if status == 401:
            return _problem_unauthorized(detail)
        if status == 403:
            return _problem_forbidden(detail)
        if status == 404:
            return _problem_not_found(detail)
        if status == 409:
            return _problem_conflict(detail)
        if status >= 500:
            return _problem_ise()
        return _problem_bad_request(detail)

    @app.errorhandler(404)
    def _h404(_: Any) -> Response:
        return _problem_not_found("not_found")

    # Map MethodNotAllowed (405) to 404 Problem for consistency with tests expecting 404 on unknown routes
    try:
        from werkzeug.exceptions import MethodNotAllowed

        from .http_errors import not_found as _problem_not_found

        try:  # optional OTEL metrics
            from opentelemetry import metrics  # type: ignore

            _http_meter = metrics.get_meter("yuplan.http")  # type: ignore
            _m_405 = _http_meter.create_counter(
                name="http.405_mapped_to_404_total",
                description="Count of MethodNotAllowed responses mapped to 404 envelope",
                unit="1",
            )
        except Exception:  # pragma: no cover
            _m_405 = None

        @app.errorhandler(MethodNotAllowed)  # type: ignore[arg-type]
        def _h405(ex: Exception) -> Response:  # pragma: no cover - exercised in failing 404 test
            app.logger.warning(
                "Mapping 405 to 404", extra={"path": request.path, "method": request.method}
            )
            if _m_405:
                try:
                    _m_405.add(1, {"method": request.method})
                except Exception:
                    pass
            return _problem_not_found("method_not_allowed")
    except Exception:  # pragma: no cover
        pass

    @app.errorhandler(Exception)
    def _h500(ex: Exception) -> Response:
        # Always return problem+json and record incident
        from .audit_events import record_audit_event
        from .http_errors import internal_server_error

        app.logger.exception("Unhandled exception (problem mode)")
        resp = internal_server_error()
        try:
            payload = resp.get_json() or {}
            if isinstance(payload, dict):
                record_audit_event("incident", incident_id=payload.get("incident_id"))
                record_audit_event(
                    "problem_response", status=payload.get("status"), type=payload.get("type")
                )
        except Exception:
            pass
        return resp

    # --- Context processor ---
    @app.context_processor
    def inject_ctx() -> dict[str, Any]:
        # expose csrf token helper if strict flag active
        def csrf_token() -> str:  # pragma: no cover - template helper
            try:
                if getattr(g, "features", {}).get("strict_csrf"):
                    from .csrf import generate_token

                    return generate_token()
            except Exception:
                return ""
            return ""

        def csrf_token_input() -> str:  # pragma: no cover - template helper
            tok = csrf_token()
            if not tok:
                return ""
            return f'<input type="hidden" name="csrf_token" value="{tok}">'  # nosec B704

        return {
            "tenant_id": getattr(g, "tenant_id", None),
            "feature_enabled": feature_enabled,
            "csrf_token": csrf_token(),
            "csrf_token_input": csrf_token_input,
        }

    # --- Logging / timing middleware ---
    log = logging.getLogger("unified")
    if not log.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(message)s"))
        log.addHandler(h)
    log.setLevel(logging.INFO)

    @app.before_request
    def _before_req() -> Response | None:
        if app.config.get("TESTING"):
            from flask import session

            role = request.headers.get("X-User-Role")
            tid = request.headers.get("X-Tenant-Id")
            uid = request.headers.get("X-User-Id")
            if role:
                session["role"] = role
                # Allow override of user id for isolation tests
                if uid and uid.isdigit():
                    session["user_id"] = int(uid)
                else:
                    session["user_id"] = 1
            if tid:
                session["tenant_id"] = int(tid) if tid.isdigit() else tid
            if tid:
                g.tenant_id = int(tid) if tid.isdigit() else tid
        # Apply impersonation (may override tenant context)
        try:
            from .impersonation import apply_impersonation  # local import to avoid cycles

            apply_impersonation()
        except Exception:  # pragma: no cover - defensive
            app.logger.warning("Failed to apply impersonation", exc_info=True)
        g._t0 = time.perf_counter()
        g.request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        _load_feature_flags_logic()
        # Strict CSRF (after header role injection so tests & role logic available)
        feats = getattr(g, "features", None)
        if feats is None:
            g.features = {}
        env_on = bool(app.config.get("YUPLAN_STRICT_CSRF"))
        g.features["strict_csrf_env"] = env_on
        g.features["strict_csrf"] = env_on
        if env_on:
            try:
                from .csrf import before_request as _csrf_before

                resp = _csrf_before()
                if resp is not None:
                    return resp
            except Exception:  # pragma: no cover
                app.logger.warning("Strict CSRF hook failed", exc_info=True)
        return None

    @app.after_request
    def _after_req(resp: Response) -> Response:
        try:
            dur_ms = int((time.perf_counter() - getattr(g, "_t0", time.perf_counter())) * 1000)
            rid = getattr(g, "request_id", str(uuid.uuid4()))
            resp.headers["X-Request-Id"] = rid
            resp.headers["X-Request-Duration-ms"] = str(dur_ms)
            if "Cache-Control" not in resp.headers:
                resp.headers["Cache-Control"] = "no-store"
            # Structured log line (security headers already added by security middleware)
            try:
                log.info(
                    {
                        "request_id": rid,
                        "tenant_id": getattr(g, "tenant_id", None),
                        "user_id": session.get("user_id"),
                        "method": request.method,
                        "path": request.path,
                        "status": resp.status_code,
                        "duration_ms": dur_ms,
                    }
                )
            except Exception:
                pass
        except Exception:
            pass
        return resp

    # --- Attach domain services (lightweight) required by some blueprints ---
    try:  # portion recommendation service
        from .portion_recommendation_service import PortionRecommendationService

        app.portion_service = PortionRecommendationService()  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover
        pass
    # Menu service
    try:
        from .menu_service import MenuServiceDB

        app.menu_service = MenuServiceDB()  # type: ignore[attr-defined]
    except Exception:
        pass
    # Metrics service
    try:
        from .service_metrics_service import ServiceMetricsService

        app.service_metrics_service = ServiceMetricsService()  # type: ignore[attr-defined]
    except Exception:
        pass
    # Diet service
    try:
        from .diet_service import DietService

        app.diet_service = DietService()  # type: ignore[attr-defined]
    except Exception:
        pass
    # Feature + tenant metadata services (needed for admin API)
    try:
        from .feature_service import FeatureService

        app.feature_service = FeatureService()  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        from .tenant_metadata_service import TenantMetadataService

        app.tenant_metadata_service = TenantMetadataService()  # type: ignore[attr-defined]
    except Exception:
        pass

    # --- Register blueprints ---
    app.register_blueprint(auth_bp)
    app.register_blueprint(notes_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(service_recommendation_bp)
    app.register_blueprint(menu_api_bp)
    app.register_blueprint(import_api_bp)
    app.register_blueprint(metrics_api_bp)
    app.register_blueprint(diet_api_bp)
    app.register_blueprint(turnus_api_bp)
    app.register_blueprint(admin_api_bp)
    app.register_blueprint(admin_audit_bp)
    app.register_blueprint(openapi_ui_bp)
    app.register_blueprint(inline_ui_bp)
    app.register_blueprint(ui_bp)
    app.register_blueprint(weekview_api_bp)
    try:
        from .superuser_impersonation_api import bp as superuser_impersonation_bp

        app.register_blueprint(superuser_impersonation_bp)
    except Exception:  # pragma: no cover
        app.logger.warning("Failed to register superuser impersonation blueprint", exc_info=True)
    # Support diagnostics blueprint
    try:
        from .support import bp as support_bp  # type: ignore

        app.register_blueprint(support_bp)
    except Exception:  # pragma: no cover
        app.logger.warning("Support blueprint not loaded", exc_info=True)
    # Legacy kommun UI (ETag-enabled /rapport, /veckovy placeholders)
    try:
        from .legacy_kommun_ui import bp as legacy_kommun_ui_bp  # type: ignore

        app.register_blueprint(legacy_kommun_ui_bp)
    except Exception:  # pragma: no cover
        app.logger.warning("Legacy kommun UI blueprint not loaded", exc_info=True)

    # Dynamic module blueprints
    for mod in cfg.default_enabled_modules:
        ref = MODULE_IMPORTS.get(mod)
        if not ref:
            continue
        module_path, obj_name = ref.split(":")
        try:
            m = import_module(module_path)
            bp = getattr(m, obj_name)
            app.register_blueprint(bp)
        except Exception as e:  # pragma: no cover
            app.logger.exception("Failed loading module %s: %s", mod, e)

    # Load rate limit registry (optional env JSON)
    try:
        from .limit_registry import load_from_env as _load_limits

        overrides = app.config.get("FEATURE_LIMITS_JSON")
        defaults = app.config.get("FEATURE_LIMITS_DEFAULTS_JSON")
        if overrides or defaults:
            _load_limits(overrides, defaults)
    except Exception:  # pragma: no cover
        pass

    # --- Error handling --- (centralized via register_error_handlers in app_errors)
    # Install support log handler late (after logging config / blueprints)
    try:
        install_support_log_handler()
    except Exception:  # pragma: no cover
        app.logger.warning("Failed to install support log handler", exc_info=True)

    # --- OpenAPI Spec Endpoint ---
    @app.get("/health")
    def health() -> dict[str, Any]:
        try:
            # list() returns dicts with name/enabled/mode; expose enabled feature names for quick glance
            enabled_feature_names = sorted(
                [f["name"] for f in feature_registry.list() if f.get("enabled")]
            )
        except Exception:
            # Fallback to internal set if present (backward compat)
            try:
                enabled_feature_names = sorted(getattr(feature_registry, "_flags", set()))  # type: ignore[arg-type]
            except Exception:
                enabled_feature_names = []
        return {
            "status": "ok",
            "modules": list(cfg.default_enabled_modules),
            "features": enabled_feature_names,
        }

    @app.get("/openapi.json")
    def openapi_spec() -> dict[str, Any]:  # pragma: no cover
        note_schema = {
            "type": "object",
            "required": ["id", "content", "private_flag"],
            "properties": {
                "id": {"type": "integer"},
                "content": {"type": "string"},
                "private_flag": {"type": "boolean"},
                "user_id": {"type": "integer", "nullable": True},
                "created_at": {"type": "string", "format": "date-time"},
                "updated_at": {"type": "string", "format": "date-time", "nullable": True},
            },
        }
        task_schema = {
            "type": "object",
            "required": ["id", "title", "task_type", "done"],
            "properties": {
                "id": {"type": "integer"},
                "title": {"type": "string"},
                "task_type": {"type": "string"},
                "done": {
                    "type": "boolean",
                    "readOnly": True,
                    "description": 'Derived legacy boolean (status=="done"). Prefer using status for writes.',
                },
                "status": {
                    "type": "string",
                    "enum": ["todo", "doing", "blocked", "done", "cancelled"],
                    "description": "Authoritative state. On create/update maps to done=(status==done).",
                },
                "menu_id": {"type": "integer", "nullable": True},
                "dish_id": {"type": "integer", "nullable": True},
                "private_flag": {"type": "boolean"},
                "assignee_id": {"type": "integer", "nullable": True},
                "creator_user_id": {"type": "integer", "nullable": True},
                "unit_id": {"type": "integer", "nullable": True},
                "created_at": {"type": "string", "format": "date-time"},
                "updated_at": {"type": "string", "format": "date-time", "nullable": True},
            },
        }

        # Legacy ErrorXXX components removed per ADR-003; keep only ProblemDetails components below
        def attach_problem(base: dict[str, Any], codes: list[str]) -> dict[str, Any]:
            r: dict[str, Any] = base.setdefault("responses", {})  # type: ignore[assignment]
            for code in codes:
                r.setdefault(code, {"$ref": f"#/components/responses/Problem{code}"})
            return base

        paths = {
            "/features": {
                "get": attach_problem(
                    {
                        "tags": ["Features"],
                        "security": [{"BearerAuth": []}],
                        "responses": {"200": {"description": "List flags"}},
                    },
                    ["401", "429", "500"],
                )
            },
            "/features/check": {
                "get": attach_problem(
                    {
                        "tags": ["Features"],
                        "security": [{"BearerAuth": []}],
                        "responses": {
                            "200": {"description": "Flag state (unknown -> enabled=false)"}
                        },
                    },
                    ["400", "401", "429", "500"],
                )
            },
            "/features/set": {
                "post": attach_problem(
                    {
                        "tags": ["Features"],
                        "security": [{"BearerAuth": []}],
                        "responses": {"200": {"description": "Updated flag"}},
                    },
                    ["400", "401", "429", "500"],
                )
            },
            "/admin/feature_flags": {
                "post": attach_problem(
                    {
                        "tags": ["Features"],
                        "security": [{"BearerAuth": []}],
                        "summary": "Toggle tenant-scoped feature flag",
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "required": ["name", "enabled"],
                                        "properties": {
                                            "name": {"type": "string"},
                                            "enabled": {"type": "boolean"},
                                            "tenant_id": {
                                                "type": "integer",
                                                "description": "Only for superuser",
                                            },
                                        },
                                    }
                                }
                            },
                        },
                        "responses": {"200": {"description": "Flag updated"}},
                    },
                    ["400", "401", "403", "429", "500"],
                ),
                "get": attach_problem(
                    {
                        "tags": ["Features"],
                        "security": [{"BearerAuth": []}],
                        "summary": "List tenant-scoped enabled feature flags",
                        "parameters": [
                            {
                                "name": "tenant_id",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "integer"},
                                "description": "Only superuser may specify",
                            }
                        ],
                        "responses": {"200": {"description": "Flags listed"}},
                    },
                    ["400", "401", "403", "429", "500"],
                ),
            },
            "/notes/": {
                "get": attach_problem(
                    {
                        "tags": ["Notes"],
                        "security": [{"BearerAuth": []}],
                        "parameters": [
                            {
                                "name": "page",
                                "in": "query",
                                "schema": {"type": "integer", "minimum": 1},
                                "required": False,
                            },
                            {
                                "name": "size",
                                "in": "query",
                                "schema": {"type": "integer", "minimum": 1, "maximum": 100},
                                "required": False,
                            },
                            {
                                "name": "sort",
                                "in": "query",
                                "schema": {"type": "string"},
                                "required": False,
                            },
                            {
                                "name": "order",
                                "in": "query",
                                "schema": {"type": "string", "enum": ["asc", "desc"]},
                                "required": False,
                            },
                        ],
                        "responses": {
                            "200": {
                                "description": "Paged notes list",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/PageResponse_Notes"
                                        }
                                    }
                                },
                            }
                        },
                    },
                    ["400", "401", "403", "500"],
                ),
                "post": attach_problem(
                    {
                        "tags": ["Notes"],
                        "security": [{"BearerAuth": []}],
                        "responses": {"200": {"description": "Create note"}},
                    },
                    ["400", "401", "403", "500"],
                ),
            },
            "/notes/{id}": {
                "parameters": [
                    {"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "put": attach_problem(
                    {
                        "tags": ["Notes"],
                        "security": [{"BearerAuth": []}],
                        "responses": {"200": {"description": "Update note"}},
                    },
                    ["400", "401", "403", "404", "500"],
                ),
                "delete": attach_problem(
                    {
                        "tags": ["Notes"],
                        "security": [{"BearerAuth": []}],
                        "responses": {"200": {"description": "Delete note"}},
                    },
                    ["401", "403", "404", "500"],
                ),
            },
            "/tasks/": {
                "get": attach_problem(
                    {
                        "tags": ["Tasks"],
                        "security": [{"BearerAuth": []}],
                        "parameters": [
                            {
                                "name": "page",
                                "in": "query",
                                "schema": {"type": "integer", "minimum": 1},
                                "required": False,
                            },
                            {
                                "name": "size",
                                "in": "query",
                                "schema": {"type": "integer", "minimum": 1, "maximum": 100},
                                "required": False,
                            },
                            {
                                "name": "sort",
                                "in": "query",
                                "schema": {"type": "string"},
                                "required": False,
                            },
                            {
                                "name": "order",
                                "in": "query",
                                "schema": {"type": "string", "enum": ["asc", "desc"]},
                                "required": False,
                            },
                        ],
                        "responses": {
                            "200": {
                                "description": "Paged tasks list",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/PageResponse_Tasks"
                                        }
                                    }
                                },
                            }
                        },
                    },
                    ["400", "401", "403", "500"],
                ),
                "post": attach_problem(
                    {
                        "tags": ["Tasks"],
                        "security": [{"BearerAuth": []}],
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/TaskCreate"}
                                }
                            },
                        },
                        "responses": {"201": {"description": "Created task"}},
                    },
                    ["400", "401", "403", "429", "500"],
                ),
            },
            "/tasks/{id}": {
                "parameters": [
                    {"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "get": attach_problem(
                    {
                        "tags": ["Tasks"],
                        "security": [{"BearerAuth": []}],
                        "responses": {"200": {"description": "Get task"}},
                    },
                    ["401", "403", "404", "500"],
                ),
                "put": attach_problem(
                    {
                        "tags": ["Tasks"],
                        "security": [{"BearerAuth": []}],
                        "responses": {"200": {"description": "Update task"}},
                    },
                    ["400", "401", "403", "404", "409", "500"],
                ),
                "delete": attach_problem(
                    {
                        "tags": ["Tasks"],
                        "security": [{"BearerAuth": []}],
                        "responses": {"200": {"description": "Delete task"}},
                    },
                    ["401", "403", "404", "500"],
                ),
            },
            "/admin/flags/legacy-cook": {
                "get": {
                    "summary": "List tenants with allow_legacy_cook_create enabled",
                    "tags": ["admin", "feature-flags"],
                    "responses": {
                        "200": {
                            "description": "Tenants with flag enabled",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/TenantListResponse"}
                                }
                            },
                        },
                        "401": {"$ref": "#/components/responses/Problem401"},
                        "403": {"$ref": "#/components/responses/Problem403"},
                    },
                    "security": [{"BearerAuth": []}],
                }
            },
            "/admin/limits": {
                "get": {
                    "summary": "Inspect effective rate limits (admin)",
                    "tags": ["admin"],
                    "parameters": [
                        {
                            "name": "tenant_id",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer"},
                            "description": "If provided include tenant overrides; omit to list only defaults",
                        },
                        {
                            "name": "name",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                            "description": "Filter to a single limit name; if absent but tenant_id supplied returns union of defaults + overrides",
                        },
                        {
                            "name": "page",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer", "minimum": 1},
                        },
                        {
                            "name": "size",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer", "minimum": 1, "maximum": 100},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Paged limits",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/PageResponse_LimitView"
                                    }
                                }
                            },
                        },
                        "400": {"$ref": "#/components/responses/Problem400"},
                        "401": {"$ref": "#/components/responses/Problem401"},
                        "403": {"$ref": "#/components/responses/Problem403"},
                    },
                    "security": [{"BearerAuth": []}],
                },
                "post": {
                    "summary": "Create or update tenant override",
                    "tags": ["admin"],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/LimitUpsertRequest"}
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Upserted",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/LimitMutationResponse"}
                                }
                            },
                        },
                        "400": {"$ref": "#/components/responses/Problem400"},
                        "401": {"$ref": "#/components/responses/Problem401"},
                        "403": {"$ref": "#/components/responses/Problem403"},
                    },
                    "security": [{"BearerAuth": []}],
                },
                "delete": {
                    "summary": "Delete tenant override",
                    "tags": ["admin"],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/LimitDeleteRequest"}
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Deleted (idempotent)",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/LimitMutationResponse"}
                                }
                            },
                        },
                        "400": {"$ref": "#/components/responses/Problem400"},
                        "401": {"$ref": "#/components/responses/Problem401"},
                        "403": {"$ref": "#/components/responses/Problem403"},
                    },
                    "security": [{"BearerAuth": []}],
                },
            },
            "/admin/audit": {
                "get": {
                    "summary": "List audit events (paged, newest first)",
                    "tags": ["admin"],
                    "parameters": [
                        {"name": "tenant_id", "in": "query", "schema": {"type": "integer"}},
                        {"name": "event", "in": "query", "schema": {"type": "string"}},
                        {
                            "name": "from",
                            "in": "query",
                            "description": "Inclusive lower bound (RFC3339).",
                            "schema": {"type": "string", "format": "date-time"},
                        },
                        {
                            "name": "to",
                            "in": "query",
                            "description": "Inclusive upper bound (RFC3339).",
                            "schema": {"type": "string", "format": "date-time"},
                        },
                        {
                            "name": "q",
                            "in": "query",
                            "description": "Case-insensitive substring match on payload (stringified).",
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "page",
                            "in": "query",
                            "schema": {"type": "integer", "minimum": 1, "default": 1},
                        },
                        {
                            "name": "size",
                            "in": "query",
                            "schema": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 100,
                                "default": 20,
                            },
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Paged audit events (descending ts)",
                            "headers": {
                                "X-Request-Id": {"$ref": "#/components/headers/X-Request-Id"}
                            },
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/PageResponse_AuditView"
                                    },
                                    "examples": {
                                        "sample": {
                                            "value": {
                                                "ok": True,
                                                "items": [
                                                    {
                                                        "id": 2,
                                                        "ts": "2025-10-05T12:02:00Z",
                                                        "tenant_id": 5,
                                                        "actor_user_id": 10,
                                                        "actor_role": "admin",
                                                        "event": "limits_upsert",
                                                        "payload": {
                                                            "limit_name": "exp",
                                                            "quota": 9,
                                                        },
                                                        "request_id": "f3a2b1f8-2e0e-4b12-9f4c-5c28a6a0c3a1",
                                                    },
                                                    {
                                                        "id": 1,
                                                        "ts": "2025-10-05T12:00:00Z",
                                                        "tenant_id": 5,
                                                        "actor_user_id": 10,
                                                        "actor_role": "admin",
                                                        "event": "limits_delete",
                                                        "payload": {"limit_name": "exp"},
                                                        "request_id": "f3a2b1f8-2e0e-4b12-9f4c-5c28a6a0c3a1",
                                                    },
                                                ],
                                                "meta": {
                                                    "page": 1,
                                                    "size": 20,
                                                    "total": 2,
                                                    "pages": 1,
                                                },
                                            }
                                        }
                                    },
                                }
                            },
                        },
                        "401": {"$ref": "#/components/responses/Problem401"},
                        "403": {"$ref": "#/components/responses/Problem403"},
                    },
                    "security": [{"BearerAuth": []}],
                }
            },
        }
        # --- ProblemDetails (pilot) ---
        problem_details_schema = {
            "type": "object",
            "required": ["type", "title", "status", "detail"],
            "properties": {
                "type": {"type": "string", "format": "uri"},
                "title": {"type": "string"},
                "status": {"type": "integer"},
                "detail": {"type": "string"},
                "instance": {"type": "string", "format": "uri", "nullable": True},
                "request_id": {
                    "type": "string",
                    "description": "Correlation id echoed as X-Request-Id header",
                },
                "incident_id": {
                    "type": "string",
                    "description": "Present only for 500 errors to correlate logs",
                    "nullable": True,
                },
                "errors": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Validation issues (422)",
                },
                "retry_after": {
                    "type": "integer",
                    "description": "Rate limit reset seconds (429)",
                    "nullable": True,
                },
            },
            "additionalProperties": True,
            "description": "RFC7807 Problem Details (pilot). Extended with request_id, incident_id, errors[]",
        }
        problem_responses = {
            code: {
                "description": f"Problem {code}",
                "headers": {"X-Request-Id": {"$ref": "#/components/headers/X-Request-Id"}},
                "content": {
                    "application/problem+json": {
                        "schema": {"$ref": "#/components/schemas/ProblemDetails"},
                        "examples": {},
                    }
                },
            }
            for code in ["400", "401", "403", "404", "409", "422", "429", "500"]
        }
        # Populate representative examples (401, 422, 500 mandatory; others minimal)
        problem_responses["401"]["content"]["application/problem+json"]["examples"][
            "unauthorized"
        ] = {
            "value": {
                "type": "https://example.com/errors/unauthorized",
                "title": "Unauthorized",
                "status": 401,
                "detail": "unauthorized",
                "request_id": "11111111-1111-1111-1111-111111111111",
            }
        }
        # Auth-specific variant showing WWW-Authenticate
        problem_responses["401"]["headers"] = {
            **problem_responses["401"].get("headers", {}),
            "WWW-Authenticate": {
                "schema": {"type": "string"},
                "description": "Auth challenge (Bearer)",
            },
        }
        problem_responses["401"]["content"]["application/problem+json"]["examples"][
            "invalid_token"
        ] = {
            "value": {
                "type": "https://example.com/errors/unauthorized",
                "title": "Unauthorized",
                "status": 401,
                "detail": "invalid_token",
                "request_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            }
        }
        problem_responses["422"]["content"]["application/problem+json"]["examples"][
            "validation"
        ] = {
            "value": {
                "type": "https://example.com/errors/validation_error",
                "title": "Unprocessable Entity",
                "status": 422,
                "detail": "validation_error",
                "errors": [{"field": "name", "message": "required"}],
                "request_id": "22222222-2222-2222-2222-222222222222",
            }
        }
        # 429 example with retry_after
        problem_responses["429"]["content"]["application/problem+json"] = problem_responses["429"][
            "content"
        ].get(
            "application/problem+json", {"schema": {"$ref": "#/components/schemas/ProblemDetails"}}
        )
        problem_responses["429"]["content"]["application/problem+json"]["examples"] = {
            "limited": {
                "value": {
                    "type": "https://example.com/errors/rate_limited",
                    "title": "Too Many Requests",
                    "status": 429,
                    "detail": "rate_limited",
                    "retry_after": 30,
                    "request_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                }
            }
        }
        problem_responses["500"]["content"]["application/problem+json"]["examples"]["incident"] = {
            "value": {
                "type": "https://example.com/errors/internal_error",
                "title": "Internal Server Error",
                "status": 500,
                "detail": "internal_error",
                "incident_id": "33333333-3333-3333-3333-333333333333",
                "request_id": "33333333-3333-3333-3333-333333333333",
            }
        }
        spec = {
            "openapi": "3.0.3",
            "info": {
                "title": "Unified Platform API",
                "version": "0.3.0",
                "description": "Problem Details (RFC7807) is the canonical error format across all endpoints. Legacy ErrorXXX components have been removed per ADR-003.",
            },
            "servers": [{"url": "/"}],
            "tags": [
                {"name": "Auth"},
                {"name": "Menus"},
                {"name": "Features"},
                {"name": "System"},
                {"name": "Notes"},
                {"name": "Tasks"},
                {"name": "weekview"},
            ],
            "components": {
                "securitySchemes": {
                    "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
                },
                "schemas": {
                    "ProblemDetails": problem_details_schema,
                    "PageMeta": {
                        "type": "object",
                        "required": ["page", "size", "total", "pages"],
                        "properties": {
                            "page": {"type": "integer"},
                            "size": {"type": "integer"},
                            "total": {"type": "integer"},
                            "pages": {"type": "integer"},
                        },
                    },
                    "PageResponse_Notes": {
                        "type": "object",
                        "required": ["ok", "items", "meta"],
                        "properties": {
                            "ok": {"type": "boolean"},
                            "items": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/Note"},
                            },
                            "meta": {"$ref": "#/components/schemas/PageMeta"},
                        },
                    },
                    "PageResponse_Tasks": {
                        "type": "object",
                        "required": ["ok", "items", "meta"],
                        "properties": {
                            "ok": {"type": "boolean"},
                            "items": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/Task"},
                            },
                            "meta": {"$ref": "#/components/schemas/PageMeta"},
                        },
                    },
                    "LimitView": {
                        "type": "object",
                        "required": ["name", "quota", "per_seconds", "source"],
                        "properties": {
                            "name": {"type": "string"},
                            "quota": {"type": "integer"},
                            "per_seconds": {"type": "integer"},
                            "source": {"type": "string", "enum": ["tenant", "default", "fallback"]},
                            "tenant_id": {"type": "integer", "nullable": True},
                        },
                    },
                    "PageResponse_LimitView": {
                        "type": "object",
                        "required": ["ok", "items", "meta"],
                        "properties": {
                            "ok": {"type": "boolean"},
                            "items": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/LimitView"},
                            },
                            "meta": {"$ref": "#/components/schemas/PageMeta"},
                        },
                    },
                    "LimitUpsertRequest": {
                        "type": "object",
                        "required": ["tenant_id", "name", "quota", "per_seconds"],
                        "properties": {
                            "tenant_id": {"type": "integer"},
                            "name": {"type": "string"},
                            "quota": {"type": "integer"},
                            "per_seconds": {"type": "integer"},
                        },
                    },
                    "LimitDeleteRequest": {
                        "type": "object",
                        "required": ["tenant_id", "name"],
                        "properties": {
                            "tenant_id": {"type": "integer"},
                            "name": {"type": "string"},
                        },
                    },
                    "LimitMutationResponse": {
                        "type": "object",
                        "required": ["ok"],
                        "properties": {
                            "ok": {"type": "boolean"},
                            "item": {"$ref": "#/components/schemas/LimitView"},
                            "updated": {"type": "boolean"},
                            "removed": {"type": "boolean"},
                        },
                    },
                    "ImportRow": {
                        "type": "object",
                        "required": ["title", "description", "priority"],
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "priority": {"type": "integer"},
                        },
                    },
                    "ImportOkResponse": {
                        "type": "object",
                        "required": ["ok", "rows", "meta"],
                        "properties": {
                            "ok": {"type": "boolean", "enum": [True]},
                            "rows": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/ImportRow"},
                            },
                            "meta": {
                                "type": "object",
                                "required": ["count"],
                                "properties": {
                                    "count": {"type": "integer"},
                                    "dry_run": {
                                        "type": "boolean",
                                        "description": "Present and true when request used ?dry_run=1",
                                    },
                                    "format": {
                                        "type": "string",
                                        "enum": ["csv", "docx", "xlsx", "menu"],
                                        "description": "Detected import format",
                                    },
                                },
                                "additionalProperties": False,
                            },
                            "dry_run": {
                                "type": "boolean",
                                "description": "Legacy alias (deprecated); prefer meta.dry_run",
                            },
                            "diff": {
                                "type": "array",
                                "items": {"type": "object"},
                                "description": "Menu dry-run diff entries (menu only)",
                            },
                        },
                        "additionalProperties": False,
                    },
                    "ImportErrorResponse": {
                        "type": "object",
                        "required": ["ok", "error", "message"],
                        "properties": {
                            "ok": {"type": "boolean", "enum": [False]},
                            "error": {
                                "type": "string",
                                "enum": ["invalid", "unsupported", "rate_limited"],
                            },
                            "message": {"type": "string"},
                            "retry_after": {"type": "integer", "nullable": True},
                            "limit": {"type": "string", "nullable": True},
                        },
                    },
                    "ImportMenuRequest": {
                        "type": "object",
                        "required": ["items"],
                        "properties": {
                            "items": {
                                "type": "array",
                                "minItems": 1,
                                "items": {
                                    "type": "object",
                                    "required": ["name"],
                                    "properties": {"name": {"type": "string"}},
                                },
                            }
                        },
                    },
                    "Note": note_schema,
                    "NoteCreate": {
                        "type": "object",
                        "required": ["content"],
                        "properties": {
                            "content": {"type": "string"},
                            "private_flag": {"type": "boolean"},
                        },
                    },
                    "Task": task_schema,
                    "TaskCreate": {
                        "type": "object",
                        "required": ["title"],
                        "properties": {
                            "title": {"type": "string"},
                            "task_type": {"type": "string"},
                            "private_flag": {"type": "boolean"},
                            "status": {"$ref": "#/components/schemas/TaskStatus"},
                        },
                    },
                    "TaskStatus": {
                        "type": "string",
                        "enum": ["todo", "doing", "blocked", "done", "cancelled"],
                    },
                    "TenantSummary": {
                        "type": "object",
                        "required": ["id", "name", "active", "features"],
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string"},
                            "active": {"type": "boolean"},
                            "features": {"type": "array", "items": {"type": "string"}},
                            "kind": {"type": "string", "nullable": True},
                            "description": {"type": "string", "nullable": True},
                        },
                    },
                    "TenantListResponse": {
                        "type": "object",
                        "required": ["ok", "tenants"],
                        "properties": {
                            "ok": {"type": "boolean"},
                            "tenants": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/TenantSummary"},
                            },
                        },
                    },
                    "AuditView": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "ts": {"type": "string", "format": "date-time"},
                            "tenant_id": {"type": "integer", "nullable": True},
                            "actor_user_id": {"type": "integer", "nullable": True},
                            "actor_role": {"type": "string"},
                            "event": {"type": "string"},
                            "payload": {"type": "object", "additionalProperties": True},
                            "request_id": {"type": "string"},
                        },
                    },
                    "PageResponse_AuditView": {
                        "type": "object",
                        "required": ["ok", "items", "meta"],
                        "properties": {
                            "ok": {"type": "boolean"},
                            "items": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/AuditView"},
                            },
                            "meta": {"$ref": "#/components/schemas/PageMeta"},
                        },
                    },
                },
                "headers": {
                    "X-Request-Id": {
                        "description": "Echoed from request or generated by server; useful for log correlation.",
                        "schema": {"type": "string"},
                        "example": "f3a2b1f8-2e0e-4b12-9f4c-5c28a6a0c3a1",
                    }
                },
                "responses": {},
            },
            "paths": paths,
        }
        # Attach Problem responses under components.responses with short names (Problem400..)
        for code, meta in problem_responses.items():
            spec["components"]["responses"][f"Problem{code}"] = meta

        # Ensure all operations include Problem responses where applicable
        for _p, methods in spec["paths"].items():
            for method, op in methods.items():
                if method.lower() not in (
                    "get",
                    "post",
                    "put",
                    "delete",
                    "patch",
                    "options",
                    "head",
                ):
                    continue
                responses = op.get("responses", {})
                for ensure_code in ["400", "401", "403", "404", "409", "422", "429", "500"]:
                    if ensure_code not in responses:
                        responses[ensure_code] = {
                            "$ref": f"#/components/responses/Problem{ensure_code}"
                        }
        # Standard 415 component (Unsupported Media Type)
        spec.setdefault("components", {}).setdefault("responses", {})["UnsupportedMediaType"] = {
            "description": "Unsupported Media Type"
        }
        # Inject Import API paths
        spec["paths"]["/import/csv"] = {
            "post": {
                "summary": "Import CSV file",
                "requestBody": {
                    "required": True,
                    "content": {
                        "multipart/form-data": {
                            "schema": {
                                "type": "object",
                                "required": ["file"],
                                "properties": {"file": {"type": "string", "format": "binary"}},
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "OK",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ImportOkResponse"}
                            }
                        },
                    },
                    "400": {"$ref": "#/components/responses/Problem400"},
                    "415": {"$ref": "#/components/responses/UnsupportedMediaType"},
                    "429": {"$ref": "#/components/responses/Problem429"},
                },
            }
        }
        spec["paths"]["/import/docx"] = {
            "post": {
                "summary": "Import DOCX table",
                "requestBody": {
                    "required": True,
                    "content": {
                        "multipart/form-data": {
                            "schema": {
                                "type": "object",
                                "required": ["file"],
                                "properties": {"file": {"type": "string", "format": "binary"}},
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "OK",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ImportOkResponse"}
                            }
                        },
                    },
                    "400": {"$ref": "#/components/responses/Problem400"},
                    "415": {"$ref": "#/components/responses/UnsupportedMediaType"},
                    "429": {"$ref": "#/components/responses/Problem429"},
                },
            }
        }
        spec["paths"]["/import/xlsx"] = {
            "post": {
                "summary": "Import XLSX spreadsheet",
                "requestBody": {
                    "required": True,
                    "content": {
                        "multipart/form-data": {
                            "schema": {
                                "type": "object",
                                "required": ["file"],
                                "properties": {"file": {"type": "string", "format": "binary"}},
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "OK",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ImportOkResponse"}
                            }
                        },
                    },
                    "400": {"$ref": "#/components/responses/Problem400"},
                    "415": {"$ref": "#/components/responses/UnsupportedMediaType"},
                    "429": {"$ref": "#/components/responses/Problem429"},
                },
            }
        }
        spec["paths"]["/import/menu"] = {
            "post": {
                "summary": "Import weekly menu (dry-run supported)",
                "parameters": [
                    {
                        "name": "dry_run",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "boolean", "default": False},
                        "description": "If true (1) perform validation + diff only (no persistence)",
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "multipart/form-data": {
                            "schema": {
                                "type": "object",
                                "required": ["file"],
                                "properties": {"file": {"type": "string", "format": "binary"}},
                            }
                        },
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ImportMenuRequest"},
                            "examples": {
                                "minimal": {
                                    "summary": "Minimal valid payload",
                                    "value": {"items": [{"name": "Spaghetti Bolognese"}]},
                                }
                            },
                        },
                    },
                },
                "responses": {
                    "200": {
                        "description": "OK",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ImportOkResponse"},
                                "examples": {
                                    "dryRun": {
                                        "value": {
                                            "ok": True,
                                            "rows": [
                                                {
                                                    "title": "Soup",
                                                    "description": "Tomato",
                                                    "priority": 1,
                                                }
                                            ],
                                            "meta": {"count": 1, "dry_run": True, "format": "menu"},
                                            "dry_run": True,
                                        }
                                    }
                                },
                            }
                        },
                    },
                    "400": {"$ref": "#/components/responses/Problem400"},
                    "415": {"$ref": "#/components/responses/UnsupportedMediaType"},
                    "429": {"$ref": "#/components/responses/Problem429"},
                },
            }
        }
        # --- Weekview Paths (Phase A skeleton; server implemented) ---
        spec["paths"]["/api/weekview"] = {
            "get": {
                "tags": ["weekview"],
                "summary": "Get week view representation",
                "parameters": [
                    {"name": "year", "in": "query", "required": True, "schema": {"type": "integer"}},
                    {
                        "name": "week",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "integer", "minimum": 1, "maximum": 53},
                    },
                    {
                        "name": "department_id",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string", "format": "uuid"},
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Week view representation",
                        "headers": {
                            "ETag": {"schema": {"type": "string"}, "description": "Weak ETag for concurrency"}
                        },
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    }
                },
            },
            "patch": {
                "tags": ["weekview"],
                "summary": "Apply changes to week view (requires If-Match)",
                "parameters": [
                    {"name": "If-Match", "in": "header", "required": True, "schema": {"type": "string"}},
                ],
                "responses": {
                    "501": {"description": "Not Implemented (Phase A)"},
                    "400": {"$ref": "#/components/responses/Problem400"},
                    "403": {"$ref": "#/components/responses/Problem403"},
                },
            },
        }
        spec["paths"]["/api/weekview/resolve"] = {
            "get": {
                "tags": ["weekview"],
                "summary": "Resolve helper",
                "parameters": [
                    {"name": "site", "in": "query", "required": True, "schema": {"type": "string"}},
                    {
                        "name": "department_id",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string", "format": "uuid"},
                    },
                    {"name": "date", "in": "query", "required": True, "schema": {"type": "string", "format": "date"}},
                ],
                "responses": {"200": {"description": "Resolution result"}},
            }
        }
        return spec

    # --- Feature flag management endpoints (regression restore) ---
    from .rate_limit import RateLimitExceeded, allow, rate_limited_response

    @app.get("/features")
    @require_roles("admin")
    def list_features() -> dict[str, Any]:  # pragma: no cover
        tid = getattr(g, "tenant_id", None)
        try:
            allow(
                tid,
                session.get("user_id"),
                "feature_flags_admin",
                30,
                testing=app.config.get("TESTING", False),
            )
        except RateLimitExceeded:
            return rate_limited_response()
        return {
            "ok": True,
            "tenant_id": tid,
            "overrides": getattr(g, "tenant_feature_flags", {}),
            "available": feature_registry.list(),
        }

    @app.get("/features/check")
    @require_roles("admin")
    def check_feature() -> dict[str, Any] | tuple[dict[str, Any], int]:  # pragma: no cover
        name = (request.args.get("name") or "").strip()
        if not name:
            return jsonify({"ok": False, "error": "name required"}), 400
        tid = getattr(g, "tenant_id", None)
        if tid is None:
            return jsonify({"ok": False, "error": "tenant required"}), 400
        try:
            allow(
                tid,
                session.get("user_id"),
                "feature_flags_admin",
                60,
                testing=app.config.get("TESTING", False),
            )
        except RateLimitExceeded:
            return rate_limited_response()
        db = get_session()
        try:
            rec = (
                db.query(TenantFeatureFlag.enabled)
                .filter(TenantFeatureFlag.tenant_id == tid, TenantFeatureFlag.name == name)
                .first()
            )
            if rec is not None:
                return {"ok": True, "name": name, "enabled": bool(rec[0])}
            return {"ok": True, "name": name, "enabled": False}
        finally:
            db.close()

    @app.post("/features/set")
    @require_roles("admin")
    def set_feature() -> dict[str, Any] | tuple[dict[str, Any], int]:  # pragma: no cover
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"ok": False, "error": "name required"}), 400
        if name not in feature_registry.list():
            feature_registry.add(name)
        enabled = bool(data.get("enabled"))
        tid = getattr(g, "tenant_id", None)
        if not tid:
            return jsonify({"ok": False, "error": "tenant required"}), 400
        try:
            allow(
                tid,
                session.get("user_id"),
                "feature_flags_admin",
                20,
                testing=app.config.get("TESTING", False),
            )
        except RateLimitExceeded:
            return rate_limited_response()
        db = get_session()
        try:
            rec = (
                db.query(TenantFeatureFlag)
                .filter(TenantFeatureFlag.tenant_id == tid, TenantFeatureFlag.name == name)
                .first()
            )
            if not rec:
                rec = TenantFeatureFlag(tenant_id=tid, name=name, enabled=enabled)
                db.add(rec)
            else:
                rec.enabled = enabled
            db.commit()
            if hasattr(g, "tenant_feature_flags"):
                g.tenant_feature_flags[name] = enabled
        finally:
            db.close()
        return {"ok": True, "name": name, "enabled": enabled}

    # --- Bootstrap superuser if env provides credentials ---
    with app.app_context():  # pragma: no cover (simple bootstrap)
        ensure_bootstrap_superuser()

    # --- Guard test endpoints (P6.2) ---
    @app.get("/_guard/editor")
    @require_roles("editor")
    def _guard_editor() -> dict[str, Any]:  # pragma: no cover - exercised in dedicated tests
        return {"ok": True, "guard": "editor"}

    @app.get("/_guard/admin")
    @require_roles("admin")
    def _guard_admin() -> dict[str, Any]:  # pragma: no cover - exercised in dedicated tests
        return {"ok": True, "guard": "admin"}

    # --- Test-only boom endpoint for incident simulation ---
    if app.config.get("TESTING"):

        @app.get("/_test/boom")
        def _test_boom() -> dict[str, Any]:  # pragma: no cover - only used in problem 500 tests
            raise RuntimeError("boom")

        # Test-only endpoints to simulate 429 without relying on limiter backends
        from .rate_limiter import (
            RateLimitError as _TestRateLimitError,  # local import to avoid prod path impact
        )

        @app.get("/_test/limit_legacy")
        def _test_limit_legacy() -> Response:  # pragma: no cover - exercised in contract tests
            # Non-pilot path -> legacy envelope with Retry-After header
            try:
                raise _TestRateLimitError(
                    "Rate limit exceeded for test_legacy", retry_after=7, limit="test_legacy"
                )
            except _TestRateLimitError as ex:  # legacy contract handler inline
                from flask import jsonify as _json

                retry = int(getattr(ex, "retry_after", 1) or 1)
                payload = {
                    "ok": False,
                    "error": "rate_limited",
                    "message": str(ex),
                    "retry_after": retry,
                    "limit": getattr(ex, "limit", None) or "none",
                }
                resp = _json(payload)
                resp.status_code = 429
                resp.headers["Retry-After"] = str(retry)
                resp.mimetype = "application/json"
                return resp

        @app.get("/diet/_test/limit_pilot")
        def _test_limit_pilot() -> None:  # pragma: no cover - exercised in contract tests
            # Pilot path -> ProblemDetails with retry_after
            raise _TestRateLimitError(
                "Rate limit exceeded for test_pilot", retry_after=9, limit="test_pilot"
            )

    # --- Test / demonstration rate limit endpoint (Pocket 7) ---
    try:
        from .http_limits import limit

        @app.get("/_limit/test")
        @limit("test_endpoint", quota=3, per_seconds=60)
        def _limit_test() -> dict[
            str, Any
        ]:  # pragma: no cover - will be covered in new rate limit tests
            return {"ok": True, "limited": False}
    except Exception:  # pragma: no cover
        pass

    return app
