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
import os

from flask import Flask, g, jsonify, request, session
from markupsafe import Markup

try:
    # Optional: if Flask-WTF is available, generate a real CSRF token
    from flask_wtf.csrf import generate_csrf  # type: ignore
except Exception:  # pragma: no cover
    generate_csrf = None  # type: ignore

from .admin_api import bp as admin_api_bp
from .admin_audit_api import bp as admin_audit_bp
from .app_authz import require_roles
from .app_errors import register_error_handlers
from .auth import bp as auth_bp, ensure_bootstrap_superuser
from .config import Config
from .db import get_session, init_engine
from .diet_api import bp as diet_api_bp
from .errors import APIError
from .export_api import bp as export_bp
from .feature_flags import FeatureRegistry
from .import_api import bp as import_api_bp
from .inline_ui import inline_ui_bp
from .menu_api import bp as menu_api_bp
from .menu_choice_api import public_bp as menu_choice_public_bp
from .metrics import set_metrics
from .metrics_logging import LoggingMetrics
from .models import TenantFeatureFlag
from .notes_api import bp as notes_bp
from .planera_api import bp as planera_api_bp
from .report_api import bp as report_api_bp
from .openapi_ui import bp as openapi_ui_bp
from .service_metrics_api import bp as metrics_api_bp
from .ui_blueprint import ui_bp
from .service_recommendation_api import bp as service_recommendation_bp
from .tasks_api import bp as tasks_bp
from .turnus_api import bp as turnus_api_bp
from .support import bp as support_bp
from .home import bp as home_bp
from .weekview_report_api import bp as weekview_report_bp
from .superuser_impersonation_api import bp as superuser_impersonation_bp
from admin.ui_blueprint import admin_ui_bp
from .legacy_kommun_ui import bp as legacy_kommun_ui_bp

# Map of module key -> import path:attr blueprint (for dynamic registration)
MODULE_IMPORTS = {
    "municipal": "modules.municipal.views:bp",
    "offshore": "modules.offshore.views:bp",
}


def create_app(config_override: dict | None = None) -> Flask:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, "templates"),
        static_url_path="/static",
        static_folder=os.path.join(base_dir, "static"),
    )

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

    # --- Jinja global: csrf_token_input ---
    @app.template_global()
    def csrf_token_input():
        """
        Returns a hidden CSRF input if CSRF is enabled, otherwise empty string.
        Prevents templates from crashing when csrf_token_input() is referenced.
        """
        enabled = bool(app.config.get("WTF_CSRF_ENABLED") or app.config.get("CSRF_ENABLED"))
        if not enabled or generate_csrf is None:
            return ""
        try:
            token = generate_csrf()
        except Exception:
            return ""
        return Markup(f'<input type="hidden" name="csrf_token" value="{token}">')

    # --- DB setup ---
    # Ensure per-app engine isolation in tests when the DB URL changes across apps
    _force = bool(app.config.get("FORCE_DB_REINIT", False)) or bool(app.config.get("TESTING", False))
    init_engine(cfg.database_url, force=_force)

    # --- Runtime alignment: ensure users.site_id exists only when not in TESTING ---
    # Contract: In TESTING app contexts, the test may create a minimal schema without site_id.
    # We align (ALTER TABLE) only for non-TESTING contexts to avoid interfering with tests.
    try:
        if not app.config.get("TESTING", False):
            with app.app_context():
                db = get_session()
                try:
                    # Only for sqlite-backed ephemeral DBs; migrations cover production.
                    if db.bind and getattr(db.bind, "dialect", None) and db.bind.dialect.name == "sqlite":
                        from sqlalchemy import text as _sql
                        cols = db.execute(_sql("PRAGMA table_info('users')")).fetchall()
                        has_site_id = any(str(c[1]) == "site_id" for c in cols)
                        if not has_site_id:
                            # Tripwire: emit stack in TESTING to discover unexpected alignment path
                            try:
                                from flask import current_app as _ca  # type: ignore
                                if bool(getattr(_ca, "config", {}).get("TESTING", False)):
                                    import traceback as _tb
                                    print("TRIPWIRE: adding users.site_id via app_factory runtime alignment\n" + "".join(_tb.format_stack(limit=12)))
                            except Exception:
                                pass
                            db.execute(_sql("ALTER TABLE users ADD COLUMN site_id TEXT NULL"))
                            db.commit()
                finally:
                    try:
                        db.close()
                    except Exception:
                        pass
    except Exception:
        # Best-effort alignment; swallow errors to avoid startup crash
        pass

    # --- Metrics backend wiring ---
    backend = app.config.get("METRICS_BACKEND") or cfg.__dict__.get("metrics_backend") or "noop"
    if backend == "log":  # minimal logging adapter
        try:
            set_metrics(LoggingMetrics())
            app.logger.info("Metrics backend initialized: log")
        except Exception:  # pragma: no cover
            app.logger.exception("Failed to initialize logging metrics backend; falling back to noop")

    # --- Feature flags ---
    feature_registry = FeatureRegistry()
    # Expose for tests manipulating registry directly
    app.feature_registry = feature_registry  # type: ignore[attr-defined]

    def _load_feature_flags_logic():
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

    # Jinja helper: role checks using canonical mapping
    @app.context_processor
    def _inject_roles():  # pragma: no cover - template usage validated in tests
        from .roles import to_canonical as _to_canonical
        def has_role(role: str) -> bool:
            try:
                return _to_canonical(str(session.get("role"))) == role
            except Exception:
                return False
        return {"has_role": has_role}

    # --- Error handling ---
    # New centralized error handlers (Pocket 6). Existing specific handlers retained below for backward compatibility.
    register_error_handlers(app)
    def _json_error(error_code: str, message: str, status: int):
        from flask import jsonify
        resp = jsonify({"ok": False, "error": error_code, "message": message})
        resp.status_code = status
        resp.headers["Content-Type"] = "application/json"
        return resp

    @app.errorhandler(APIError)
    def _handle_api_error(ex: APIError):
        return _json_error(ex.error_code, ex.message, ex.status_code)

    @app.errorhandler(404)
    def _h404(_):
        # Return RFC7807 problem+json for 404 to satisfy UI tests
        resp = jsonify({
            "type": "https://example.com/errors/not_found",
            "title": "Not Found",
            "status": 404,
            "detail": "Not Found",
            "instance": request.path,
        })
        resp.status_code = 404
        resp.mimetype = "application/problem+json"
        return resp

    @app.errorhandler(400)
    def _h400(_):
        return _json_error("bad_request", "Bad Request", 400)

    @app.errorhandler(401)
    def _h401(_):
        # Always emit RFC7807 for Unauthorized to satisfy Pocket 6 contracts
        try:
            from flask import jsonify, g
            resp = jsonify({
                "type": "https://example.com/errors/unauthorized",
                "title": "Unauthorized",
                "status": 401,
                "detail": "unauthorized",
                "instance": request.path,
                "request_id": getattr(g, "request_id", None),
            })
            resp.status_code = 401
            resp.mimetype = "application/problem+json"
            try:
                from .audit_events import record_audit_event
                record_audit_event("problem_response", status=401, type="unauthorized", path=request.path)
            except Exception:
                pass
            return resp
        except Exception:
            # Fallback: legacy envelope if jsonify or context unavailable
            return _json_error("unauthorized", "authentication required", 401)

    @app.errorhandler(403)
    def _h403(_):
        return _json_error("forbidden", "Forbidden", 403)

    @app.errorhandler(409)
    def _h409(_):
        return _json_error("conflict", "Conflict", 409)

    @app.errorhandler(Exception)
    def _h500(ex):
        if isinstance(ex, APIError):
            return _handle_api_error(ex)
        app.logger.exception("Unhandled exception")
        # Problem-only mode: return RFC7807 for incidents and record audit event
        try:
            if os.environ.get("YUPLAN_PROBLEM_ONLY") == "1":
                from flask import jsonify, g
                import uuid as _uuid
                incident_id = str(_uuid.uuid4())
                resp = jsonify({
                    "type": "https://example.com/errors/internal_error",
                    "title": "Internal Server Error",
                    "status": 500,
                    "detail": "incident",
                    "instance": request.path,
                    "request_id": getattr(g, "request_id", None),
                    "incident_id": incident_id,
                })
                resp.status_code = 500
                resp.mimetype = "application/problem+json"
                try:
                    from .audit_events import record_audit_event
                    record_audit_event("incident", incident_id=incident_id, path=request.path)
                except Exception:
                    pass
                return resp
        except Exception:
            pass
        return _json_error("internal_error", "Internal Server Error", 500)

    # --- Context processor ---
    @app.context_processor
    def inject_ctx():
        def has_role(*roles: str) -> bool:
            try:
                r = session.get("role")
                if not r:
                    return False
                return any(r == role for role in roles)
            except Exception:
                return False
        return {"tenant_id": getattr(g, "tenant_id", None), "feature_enabled": feature_enabled, "has_role": has_role}

    # --- Logging / timing middleware ---
    log = logging.getLogger("unified")
    if not log.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(message)s"))
        log.addHandler(h)
    log.setLevel(logging.INFO)

    @app.before_request
    def _before_req():
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
            # Lenient default tenant context for admin endpoints in tests
            try:
                if not session.get("tenant_id") and (request.path or "").startswith("/admin"):
                    # Use non-zero tenant_id so get_session() treats it as present
                    session["tenant_id"] = 1
                    g.tenant_id = 1
                
            except Exception:
                pass
        g._t0 = time.perf_counter()
        g.request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        _load_feature_flags_logic()
        # Back-compat: expose feature flags under g.features for templates
        try:
            g.features = getattr(g, "tenant_feature_flags", {})  # type: ignore[attr-defined]
        except Exception:
            pass
        # Enforce CSRF for /admin mutations (lightweight)
        if not app.config.get("TESTING"):
            try:
                from .csrf import require_csrf_for_admin_mutations
                resp = require_csrf_for_admin_mutations(request)
                if resp is not None:
                    return resp
            except Exception:
                # Do not crash request pipeline; fall through to handlers
                pass

    # Strict CSRF rollout gate: register per-request check honoring dynamic config
    @app.before_request
    def _strict_csrf_gate():
        try:
            if app.config.get("YUPLAN_STRICT_CSRF", False):
                from .csrf import before_request as _csrf_before
                result = _csrf_before()
                if result is not None:
                    return result
        except Exception:
            # Fail open to avoid breaking flows unexpectedly
            return None

    @app.after_request
    def _after_req(resp):
        try:
            dur_ms = int((time.perf_counter() - getattr(g, "_t0", time.perf_counter())) * 1000)
            rid = getattr(g, "request_id", str(uuid.uuid4()))
            resp.headers["X-Request-Id"] = rid
            resp.headers["X-Request-Duration-ms"] = str(dur_ms)
            if "Cache-Control" not in resp.headers:
                resp.headers["Cache-Control"] = "no-store"
            csp = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
            resp.headers.setdefault("Content-Security-Policy", csp)
            resp.headers.setdefault("X-Content-Type-Options", "nosniff")
            resp.headers.setdefault("X-Frame-Options", "DENY")
            resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
            resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
            if not app.config.get("TESTING") and not app.config.get("DEBUG"):
                resp.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload")
            # Minimal CORS for OpenAPI: echo allowed Origin for /openapi.json only
            try:
                if request.path.endswith("/openapi.json"):
                    origin = request.headers.get("Origin")
                    allowed = app.config.get("CORS_ALLOWED_ORIGINS") or []
                    if origin and origin in allowed:
                        resp.headers["Access-Control-Allow-Origin"] = origin
                        # Ensure Vary includes Origin (in addition to any existing values)
                        vary = resp.headers.get("Vary")
                        if not vary:
                            resp.headers["Vary"] = "Origin"
                        elif "Origin" not in [v.strip() for v in vary.split(",")]:
                            resp.headers["Vary"] = vary + ", Origin"
            except Exception:
                pass
            # Structured log line
            try:
                log.info({
                    "request_id": rid,
                    "tenant_id": getattr(g, "tenant_id", None),
                    "user_id": session.get("user_id"),
                    "method": request.method,
                    "path": request.path,
                    "status": resp.status_code,
                    "duration_ms": dur_ms,
                })
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
    # Public menu-choice endpoints (editor/admin)
    app.register_blueprint(menu_choice_public_bp)
    app.register_blueprint(import_api_bp)
    app.register_blueprint(metrics_api_bp)
    app.register_blueprint(diet_api_bp)
    app.register_blueprint(planera_api_bp)
    app.register_blueprint(report_api_bp)
    app.register_blueprint(turnus_api_bp)
    app.register_blueprint(weekview_report_bp)
    app.register_blueprint(admin_api_bp)
    app.register_blueprint(admin_audit_bp)
    app.register_blueprint(openapi_ui_bp)
    app.register_blueprint(inline_ui_bp)
    app.register_blueprint(support_bp)
    # Basic home + UI login routes
    app.register_blueprint(home_bp)
    # Unified UI/Portal routes (week view, planera day, etc.)
    app.register_blueprint(ui_bp)
    # Admin UI routes (dashboard, departments, menu import)
    app.register_blueprint(admin_ui_bp)
    # Legacy Kommun UI adapter (provides /kommun/* endpoints used by ETag tests)
    app.register_blueprint(legacy_kommun_ui_bp)
    # Superuser impersonation endpoints
    app.register_blueprint(superuser_impersonation_bp)
    # Test-only endpoints (rate limit contracts, etc.)
    if app.config.get("TESTING"):
        try:
            from .test_endpoints import bp as test_endpoints_bp
            app.register_blueprint(test_endpoints_bp)
        except Exception:
            pass

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

    # --- Dashboard routes ---
    from flask import render_template, redirect
    @app.get("/dashboard")
    def dashboard():  # pragma: no cover - exercised in UI tests
        # Require feature flag
        if not feature_enabled("ff.dashboard.enabled"):
            # Return 404 ProblemDetails
            resp = jsonify({
                "type": "https://example.com/errors/not_found",
                "title": "Not Found",
                "status": 404,
                "detail": "Dashboard disabled",
                "instance": request.path,
            })
            resp.status_code = 404
            resp.mimetype = "application/problem+json"
            return resp
        # Require login
        if not session.get("user_id") or not session.get("tenant_id"):
            return redirect("/")
        # RBAC: admin or editor only
        from .roles import to_canonical as _to_canonical
        role = _to_canonical(str(session.get("role")))
        if role not in ("admin", "editor"):
            # Forbidden ProblemDetails (minimal)
            resp = jsonify({
                "type": "https://example.com/errors/forbidden",
                "title": "Forbidden",
                "status": 403,
                "detail": "forbidden",
                "instance": request.path,
            })
            resp.status_code = 403
            resp.mimetype = "application/problem+json"
            return resp
        return render_template("ui/dashboard.html")

    @app.get("/")
    def root():  # pragma: no cover - exercised in tests
        try:
            # If logged in and dashboard enabled, jump to dashboard
            if session.get("user_id") and session.get("tenant_id"):
                if feature_enabled("ff.dashboard.enabled"):
                    return redirect("/dashboard")
        except Exception:
            pass
        # Otherwise show home page or login redirect
        try:
            return render_template("home.html")
        except Exception:
            return redirect("/home")

    # --- OpenAPI Spec Endpoint ---
    @app.get("/openapi.json")
    def openapi_spec():  # pragma: no cover
        error_schema = {
            "type": "object",
            "required": ["error", "message"],
            "properties": {
                "error": {"type": "string", "example": "validation_error"},
                "message": {"type": "string", "example": "Invalid input"}
            },
            "additionalProperties": False
        }
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
            }
        }
        task_schema = {
            "type": "object",
            "required": ["id", "title", "task_type", "done"],
            "properties": {
                "id": {"type": "integer"},
                "title": {"type": "string"},
                "task_type": {"type": "string"},
                "done": {"type": "boolean", "readOnly": True, "description": 'Derived legacy boolean (status=="done"). Prefer using status for writes.'},
                "status": {"type": "string", "enum": ["todo","doing","blocked","done","cancelled"], "description": "Authoritative state. On create/update maps to done=(status==done)."},
                "menu_id": {"type": "integer", "nullable": True},
                "dish_id": {"type": "integer", "nullable": True},
                "private_flag": {"type": "boolean"},
                "assignee_id": {"type": "integer", "nullable": True},
                "creator_user_id": {"type": "integer", "nullable": True},
                "unit_id": {"type": "integer", "nullable": True},
                "created_at": {"type": "string", "format": "date-time"},
                "updated_at": {"type": "string", "format": "date-time", "nullable": True},
            }
        }
        # Reusable error responses (referenced in tests)
        def err_resp(desc, example):
            return {
                "description": desc,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Error"},
                        "examples": {example: {"value": {"error": example, "message": desc}}}
                    }
                }
            }
        reusable = {
            "Error400": err_resp("Bad Request", "bad_request"),
            # Override 401/403 with richer examples below, still keep mapping for legacy references
            "Error401": {
                "description": "Unauthorized",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Error"},
                        "examples": {
                            "unauthorized": {
                                "value": {"error": "unauthorized", "message": "Bearer token missing or invalid"}
                            }
                        }
                    }
                }
            },
            "Error403": {
                "description": "Forbidden",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["error","message"],
                            "properties": {
                                "error": {"type":"string"},
                                "message": {"type":"string"},
                                "required_role": {"type":"string"}
                            }
                        },
                        "examples": {
                            "forbidden": {
                                "value": {"error": "forbidden", "message": "Requires role admin", "required_role": "admin"}
                            }
                        }
                    }
                }
            },
            "Error404": err_resp("Not Found", "not_found"),
            "Error409": err_resp("Conflict", "conflict"),
            "Error429": {
                "description": "Rate Limited",
                "headers": {
                    "Retry-After": {"schema": {"type": "integer"}, "description": "Seconds until new request may succeed"}
                },
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["error","message"],
                            "properties": {
                                "error": {"type":"string"},
                                "message": {"type":"string"},
                                "retry_after": {"type":"integer","nullable":True, "description": "Ceiled seconds until next permitted attempt (min 1 when present)"}
                            }
                        },
                        "examples": {
                            "rateLimited": {
                                "value": {"error": "rate_limited", "message": "Too many requests", "retry_after": 30}
                            }
                        }
                    }
                }
            },
            "Error500": err_resp("Internal Server Error", "internal_error"),
            # RFC7807 reusable responses
            "Problem401": {
                "description": "Unauthorized",
                "content": {
                    "application/problem+json": {
                        "schema": {"$ref": "#/components/schemas/ProblemDetails"},
                        "examples": {
                            "unauthorized": {
                                "value": {"type": "https://example.com/errors/unauthorized", "title": "Unauthorized", "status": 401, "detail": "unauthorized"}
                            }
                        }
                    }
                }
            },
            "Problem403": {
                "description": "Forbidden",
                "content": {
                    "application/problem+json": {
                        "schema": {"$ref": "#/components/schemas/ProblemDetails"},
                        "examples": {
                            "forbidden": {
                                "value": {"type": "https://example.com/errors/forbidden", "title": "Forbidden", "status": 403, "detail": "forbidden", "required_role": "admin"}
                            }
                        }
                    }
                }
            },
            "Problem429": {
                "description": "Rate Limited",
                "headers": {
                    "Retry-After": {"schema": {"type": "integer"}, "description": "Seconds until new request may succeed"}
                },
                "content": {
                    "application/problem+json": {
                        "schema": {"$ref": "#/components/schemas/ProblemDetails"},
                        "examples": {
                            "rateLimited": {
                                "value": {"type": "https://example.com/errors/rate_limited", "title": "Too Many Requests", "status": 429, "detail": "rate_limited"}
                            }
                        }
                    }
                }
            },
        }
        def attach(base: dict, codes: list[str]):
            r = base.setdefault("responses", {})
            for code in codes:
                ref_name = f"Error{code}" if code in ("400","401","403","404","409","500") else None
                if ref_name and ref_name in reusable:
                    r.setdefault(code, {"$ref": f"#/components/responses/{ref_name}"})
                else:  # fallback
                    r.setdefault(code, {"description": code, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}})
            return base

        paths = {
            "/features": {"get": attach({"tags": ["Features"], "security": [{"BearerAuth": []}], "responses": {"200": {"description": "List flags"}}}, ["401","429","500"])},
            "/features/check": {"get": attach({"tags": ["Features"], "security": [{"BearerAuth": []}], "responses": {"200": {"description": "Flag state (unknown -> enabled=false)"}}}, ["400","401","429","500"])},
            "/features/set": {"post": attach({"tags": ["Features"], "security": [{"BearerAuth": []}], "responses": {"200": {"description": "Updated flag"}}}, ["400","401","429","500"])},
            "/admin/feature_flags": {
                "post": attach({
                    "tags": ["Features"],
                    "security": [{"BearerAuth": []}],
                    "summary": "Toggle tenant-scoped feature flag",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {
                            "type": "object", "required": ["name","enabled"],
                            "properties": {
                                "name": {"type": "string"},
                                "enabled": {"type": "boolean"},
                                "tenant_id": {"type": "integer", "description": "Only for superuser"}
                            }
                        }}}
                    },
                    "responses": {"200": {"description": "Flag updated"}}
                }, ["400","401","403","429","500"]),
                "get": attach({
                    "tags": ["Features"],
                    "security": [{"BearerAuth": []}],
                    "summary": "List tenant-scoped enabled feature flags",
                    "parameters": [
                        {"name": "tenant_id","in":"query","required": False,"schema": {"type":"integer"}, "description":"Only superuser may specify"}
                    ],
                    "responses": {"200": {"description": "Flags listed"}},
                }, ["400","401","403","429","500"])
            },
            "/notes/": {
                "get": attach({
                    "tags": ["Notes"],
                    "security": [{"BearerAuth": []}],
                    "parameters": [
                        {"name": "page", "in": "query", "schema": {"type": "integer", "minimum": 1}, "required": False},
                        {"name": "size", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 100}, "required": False},
                        {"name": "sort", "in": "query", "schema": {"type": "string"}, "required": False},
                        {"name": "order", "in": "query", "schema": {"type": "string", "enum": ["asc","desc"]}, "required": False},
                    ],
                    "responses": {"200": {"description": "Paged notes list", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/PageResponse_Notes"}}}}}
                }, ["400","401","403","500"]),
                "post": attach({"tags": ["Notes"], "security": [{"BearerAuth": []}], "responses": {"200": {"description": "Create note"}}}, ["400","401","403","500"]),
            },
            "/notes/{id}": {
                "parameters": [{"name":"id","in":"path","required":True,"schema":{"type":"integer"}}],
                "put": attach({"tags": ["Notes"], "security": [{"BearerAuth": []}], "responses": {"200": {"description": "Update note"}}}, ["400","401","403","404","500"]),
                "delete": attach({"tags": ["Notes"], "security": [{"BearerAuth": []}], "responses": {"200": {"description": "Delete note"}}}, ["401","403","404","500"]),
            },
            "/tasks/": {
                "get": attach({
                    "tags": ["Tasks"],
                    "security": [{"BearerAuth": []}],
                    "parameters": [
                        {"name": "page", "in": "query", "schema": {"type": "integer", "minimum": 1}, "required": False},
                        {"name": "size", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 100}, "required": False},
                        {"name": "sort", "in": "query", "schema": {"type": "string"}, "required": False},
                        {"name": "order", "in": "query", "schema": {"type": "string", "enum": ["asc","desc"]}, "required": False},
                    ],
                    "responses": {"200": {"description": "Paged tasks list", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/PageResponse_Tasks"}}}}}
                }, ["400","401","403","500"]),
                "post": attach({
                    "tags": ["Tasks"],
                    "security": [{"BearerAuth": []}],
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/TaskCreate"}}}},
                    "responses": {"201": {"description": "Created task"}}
                }, ["400","401","403","429","500"]),
            },
            "/tasks/{id}": {
                "parameters": [{"name":"id","in":"path","required":True,"schema":{"type":"integer"}}],
                "get": attach({"tags": ["Tasks"], "security": [{"BearerAuth": []}], "responses": {"200": {"description": "Get task"}}}, ["401","403","404","500"]),
                "put": attach({"tags": ["Tasks"], "security": [{"BearerAuth": []}], "responses": {"200": {"description": "Update task"}}}, ["400","401","403","404","409","500"]),
                "delete": attach({"tags": ["Tasks"], "security": [{"BearerAuth": []}], "responses": {"200": {"description": "Delete task"}}}, ["401","403","404","500"]),
            },
            "/admin/flags/legacy-cook": {
                "get": {
                    "summary": "List tenants with allow_legacy_cook_create enabled",
                    "tags": ["admin", "feature-flags"],
                    "responses": {
                        "200": {
                            "description": "Tenants with flag enabled",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/TenantListResponse"}}}
                        },
                        "401": {"$ref": "#/components/responses/Error401"},
                        "403": {"$ref": "#/components/responses/Error403"}
                    },
                    "security": [{"BearerAuth": []}]
                }
            },
            "/admin/limits": {
                "get": {
                    "summary": "Inspect effective rate limits (admin)",
                    "tags": ["admin"],
                    "parameters": [
                        {"name": "tenant_id", "in": "query", "required": False, "schema": {"type": "integer"}, "description": "If provided include tenant overrides; omit to list only defaults"},
                        {"name": "name", "in": "query", "required": False, "schema": {"type": "string"}, "description": "Filter to a single limit name; if absent but tenant_id supplied returns union of defaults + overrides"},
                        {"name": "page", "in": "query", "required": False, "schema": {"type": "integer", "minimum": 1}},
                        {"name": "size", "in": "query", "required": False, "schema": {"type": "integer", "minimum": 1, "maximum": 100}}
                    ],
                    "responses": {
                        "200": {"description": "Paged limits", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/PageResponse_LimitView"}}}},
                        "400": {"$ref": "#/components/responses/Error400"},
                        "401": {"$ref": "#/components/responses/Error401"},
                        "403": {"$ref": "#/components/responses/Error403"}
                    },
                    "security": [{"BearerAuth": []}]
                },
                "post": {
                    "summary": "Create or update tenant override",
                    "tags": ["admin"],
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/LimitUpsertRequest"}}}},
                    "responses": {
                        "200": {"description": "Upserted", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/LimitMutationResponse"}}}},
                        "400": {"$ref": "#/components/responses/Error400"},
                        "401": {"$ref": "#/components/responses/Error401"},
                        "403": {"$ref": "#/components/responses/Error403"}
                    },
                    "security": [{"BearerAuth": []}]
                },
                "delete": {
                    "summary": "Delete tenant override",
                    "tags": ["admin"],
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/LimitDeleteRequest"}}}},
                    "responses": {
                        "200": {"description": "Deleted (idempotent)", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/LimitMutationResponse"}}}},
                        "400": {"$ref": "#/components/responses/Error400"},
                        "401": {"$ref": "#/components/responses/Error401"},
                        "403": {"$ref": "#/components/responses/Error403"}
                    },
                    "security": [{"BearerAuth": []}]
                }
            },
            "/admin/audit": {
                "get": {
                    "summary": "List audit events (paged, newest first)",
                    "tags": ["admin"],
                    "parameters": [
                        {"name": "tenant_id", "in": "query", "schema": {"type": "integer"}},
                        {"name": "event", "in": "query", "schema": {"type": "string"}},
                        {"name": "from", "in": "query", "description": "Inclusive lower bound (RFC3339).", "schema": {"type": "string", "format": "date-time"}},
                        {"name": "to", "in": "query", "description": "Inclusive upper bound (RFC3339).", "schema": {"type": "string", "format": "date-time"}},
                        {"name": "q", "in": "query", "description": "Case-insensitive substring match on payload (stringified).", "schema": {"type": "string"}},
                        {"name": "page", "in": "query", "schema": {"type": "integer", "minimum": 1, "default": 1}},
                        {"name": "size", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}},
                    ],
                    "responses": {
                        "200": {
                            "description": "Paged audit events (descending ts)",
                            "headers": {"X-Request-Id": {"$ref": "#/components/headers/X-Request-Id"}},
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/PageResponse_AuditView"},
                                    "examples": {
                                        "sample": {
                                            "value": {
                                                "ok": True,
                                                "items": [
                                                    {"id": 2, "ts": "2025-10-05T12:02:00Z", "tenant_id": 5, "actor_user_id": 10, "actor_role": "admin", "event": "limits_upsert", "payload": {"limit_name": "exp", "quota": 9}, "request_id": "f3a2b1f8-2e0e-4b12-9f4c-5c28a6a0c3a1"},
                                                    {"id": 1, "ts": "2025-10-05T12:00:00Z", "tenant_id": 5, "actor_user_id": 10, "actor_role": "admin", "event": "limits_delete", "payload": {"limit_name": "exp"}, "request_id": "f3a2b1f8-2e0e-4b12-9f4c-5c28a6a0c3a1"}
                                                ],
                                                "meta": {"page": 1, "size": 20, "total": 2, "pages": 1}
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "401": {"$ref": "#/components/responses/Error401"},
                        "403": {"$ref": "#/components/responses/Error403"}
                    },
                    "security": [{"BearerAuth": []}]
                }
            },
            # ---- Phase-B: Admin departments + Alt2 (spec-only paths under /api/admin) ----
            "/api/admin/departments/{id}": {
                "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "put": attach({
                    "tags": ["admin"],
                    "summary": "Update department",
                    "parameters": [
                        {"name": "If-Match", "in": "header", "required": True, "schema": {"type": "string"}, "description": "ETag for optimistic concurrency"}
                    ],
                    "responses": {"200": {"description": "Updated"}}
                }, ["400","401","403","412","500"])
            },
            "/api/admin/alt2": {
                "put": attach({
                    "tags": ["admin"],
                    "summary": "Alt2 bulk upsert",
                    "parameters": [
                        {"name": "If-Match", "in": "header", "required": True, "schema": {"type": "string"}, "description": "Collection ETag for concurrency"}
                    ],
                    "responses": {"200": {"description": "Updated"}}
                }, ["400","401","403","412","500"])
            },
            # ---- Phase-2: Minimal Admin paths (users, feature-flags, roles) ----
            "/admin/users": {
                "get": attach({
                    "tags": ["admin"],
                    "security": [{"BearerAuth": []}],
                    "summary": "List users (tenant scoped)",
                    "description": "pagination stub — currently ignored by API response. Response header X-Users-Deleted-Total returns the count of soft-deleted users for the current tenant. Errors on admin routes use RFC7807 (application/problem+json).",
                    "parameters": [
                        {"name": "q", "in": "query", "required": False, "schema": {"type": "string"}, "description": "Filter by email (case-insensitive substring)"},
                        {"name": "page", "in": "query", "required": False, "schema": {"type": "integer", "minimum": 1}},
                        {"name": "size", "in": "query", "required": False, "schema": {"type": "integer", "minimum": 1, "maximum": 100}}
                    ],
                    "responses": {
                        "200": {
                            "description": "Users",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "required": ["items", "total"],
                                        "properties": {
                                            "items": {"type": "array", "items": {"$ref": "#/components/schemas/User"}},
                                            "total": {"type": "integer"}
                                        },
                                        "additionalProperties": False
                                    },
                                    "examples": {
                                        "ok": {
                                            "value": {
                                                "items": [
                                                    {"id": "u1", "email": "a@ex", "role": "admin"}
                                                ],
                                                "total": 1
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }, ["401", "403"]),
                "post": attach({
                    "tags": ["admin"],
                    "security": [{"BearerAuth": [], "CsrfToken": []}],
                    "summary": "Create user",
                    "description": "On success, an audit event (user_create) is recorded. Errors on admin routes use RFC7807 (application/problem+json).",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["email", "role"],
                                    "properties": {
                                        "email": {"type": "string", "format": "email"},
                                        "role": {"type": "string", "enum": ["admin", "editor", "viewer"]}
                                    },
                                    "additionalProperties": False
                                }
                            }
                        }
                    },
                    "responses": {
                        "201": {"description": "Created", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/User"}}}},
                        "422": {
                            "description": "Validation error",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Error"},
                                    "examples": {
                                        "invalidEmail": {"value": {"ok": False, "error": "invalid", "message": "validation_error", "invalid_params": [{"name":"email","reason":"invalid_format"}]}},
                                        "invalidRole": {"value": {"ok": False, "error": "invalid", "message": "validation_error", "invalid_params": [{"name":"role","reason":"invalid_enum","allowed":["admin","editor","viewer"]}]}},
                                        "additional": {"value": {"ok": False, "error": "invalid", "message": "validation_error", "invalid_params": [{"name":"extra","reason":"additional_properties_not_allowed"}]}},
                                        "duplicateEmail": {"value": {"ok": False, "error": "invalid", "message": "validation_error", "invalid_params": [{"name":"email","reason":"duplicate"}]}}
                                    }
                                }
                            }
                        }
                    }
                }, ["401", "403", "422"])  # 422 via default fallback schema
            },
            "/admin/users/{user_id}": {
                "parameters": [
                    {"name": "user_id", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                "put": attach({
                    "tags": ["admin"],
                    "security": [{"BearerAuth": [], "CsrfToken": []}],
                    "summary": "Replace user (strict)",
                    "description": "Full-body replace of user email and role. Errors on admin routes use RFC7807 (application/problem+json).",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["email", "role"],
                                    "properties": {
                                        "email": {"type": "string", "format": "email"},
                                        "role": {"type": "string", "enum": ["admin","editor","viewer"]}
                                    },
                                    "additionalProperties": False
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/UserWithRole"},
                                    "examples": {"ok": {"value": {"id": "u1", "email": "a2@ex", "role": "editor", "updated_at": "2025-01-01T12:00:00+00:00"}}}
                                }
                            }
                        },
                        "404": {
                            "description": "Not found",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}, "examples": {"userMissing": {"value": {"ok": False, "error": "not_found", "message": "user not found"}}}}}
                        },
                        "422": {
                            "description": "Validation error",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}, "examples": {
                                "missing": {"value": {"ok": False, "error": "invalid", "message": "validation_error", "invalid_params": [{"name":"email","reason":"required"},{"name":"role","reason":"required"}]}},
                                "invalidEmail": {"value": {"ok": False, "error": "invalid", "message": "validation_error", "invalid_params": [{"name":"email","reason":"invalid_format"}]}},
                                "invalidRole": {"value": {"ok": False, "error": "invalid", "message": "validation_error", "invalid_params": [{"name":"role","reason":"invalid_enum","allowed":["admin","editor","viewer"]}]}},
                                "duplicateEmail": {"value": {"ok": False, "error": "invalid", "message": "validation_error", "invalid_params": [{"name":"email","reason":"duplicate"}]}}
                            }}}
                        }
                    }
                }, ["401", "403", "404", "422"]),
                "patch": attach({
                    "tags": ["admin"],
                    "security": [{"BearerAuth": [], "CsrfToken": []}],
                    "summary": "Update user (email/role)",
                    "description": "When role changes, an audit event (user_update_role) is recorded. Errors on admin routes use RFC7807 (application/problem+json).",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "email": {"type": "string", "format": "email"},
                                        "role": {"type": "string", "enum": ["admin","editor","viewer"]}
                                    },
                                    "additionalProperties": False
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/UserWithRole"},
                                    "examples": {
                                        "ok": {"value": {"id": "u1", "email": "a2@ex", "role": "editor", "updated_at": "2025-01-01T12:00:00+00:00"}}
                                    }
                                }
                            }
                        },
                        "404": {
                            "description": "Not found",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}, "examples": {"userMissing": {"value": {"ok": False, "error": "not_found", "message": "user not found"}}}}}
                        },
                        "422": {
                            "description": "Validation error",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}, "examples": {
                                "invalidEmail": {"value": {"ok": False, "error": "invalid", "message": "validation_error", "invalid_params": [{"name":"email","reason":"invalid_format"}]}},
                                "invalidRole": {"value": {"ok": False, "error": "invalid", "message": "validation_error", "invalid_params": [{"name":"role","reason":"invalid_enum","allowed":["admin","editor","viewer"]}]}},
                                "duplicateEmail": {"value": {"ok": False, "error": "invalid", "message": "validation_error", "invalid_params": [{"name":"email","reason":"duplicate"}]}}
                            }}}
                        }
                    }
                }, ["401", "403", "404", "422"]),
                "delete": attach({
                    "tags": ["admin"],
                    "security": [{"BearerAuth": [], "CsrfToken": []}],
                    "summary": "Soft-delete user",
                    "description": "Errors on admin routes use RFC7807 (application/problem+json).",
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "required": ["id", "deleted_at"],
                                        "properties": {
                                            "id": {"type": "string"},
                                            "deleted_at": {"type": "string", "format": "date-time"}
                                        },
                                        "additionalProperties": False
                                    },
                                    "examples": {
                                        "ok": {"value": {"id": "u1", "deleted_at": "2025-01-01T12:00:00+00:00"}}
                                    }
                                }
                            }
                        },
                        "404": {
                            "description": "Not found",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Error"},
                                    "examples": {"userMissing": {"value": {"ok": False, "error": "not_found", "message": "user not found"}}}
                                }
                            }
                        }
                    }
                }, ["401", "403", "404"])  # CSRF + RBAC enforced
            },
            "/admin/feature-flags": {
                "get": attach({
                    "tags": ["admin", "feature-flags"],
                    "security": [{"BearerAuth": []}],
                    "summary": "List feature flags (tenant scoped)",
                    "description": "pagination stub — currently ignored by API response. Errors on admin routes use RFC7807 (application/problem+json).",
                    "parameters": [
                        {"name": "q", "in": "query", "required": False, "schema": {"type": "string"}, "description": "Quick filter"},
                        {"name": "page", "in": "query", "required": False, "schema": {"type": "integer", "minimum": 1}},
                        {"name": "size", "in": "query", "required": False, "schema": {"type": "integer", "minimum": 1, "maximum": 100}}
                    ],
                    "responses": {
                        "200": {
                            "description": "Flags",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "required": ["items", "total"],
                                        "properties": {
                                            "items": {"type": "array", "items": {"$ref": "#/components/schemas/FeatureFlag"}},
                                            "total": {"type": "integer"}
                                        },
                                        "additionalProperties": False
                                    },
                                    "examples": {
                                        "ok": {
                                            "value": {
                                                "items": [
                                                    {"key": "beta-ui", "enabled": True, "notes": "Activated", "updated_at": "2025-01-01T12:00:00+00:00"}
                                                ],
                                                "total": 1
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }, ["401", "403"]),
            },
            "/admin/feature-flags/{key}": {
                "parameters": [
                    {"name": "key", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                "patch": attach({
                    "tags": ["admin", "feature-flags"],
                    "security": [{"BearerAuth": [], "CsrfToken": []}],
                    "summary": "Update feature flag (enabled/notes)",
                    "description": "On change, an audit event (feature_flag_update) is recorded. Errors on admin routes use RFC7807 (application/problem+json).",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "enabled": {"type": "boolean"},
                                        "notes": {"type": "string", "maxLength": 500}
                                    },
                                    "additionalProperties": False
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {"description": "OK", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/FeatureFlag"}}}},
                        "404": {
                            "description": "Not found",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}, "examples": {"flagMissing": {"value": {"ok": False, "error": "not_found", "message": "feature flag not found"}}}}}
                        },
                        "422": {
                            "description": "Validation error",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}, "examples": {
                                "enabledType": {"value": {"ok": False, "error": "invalid", "message": "validation_error", "invalid_params": [{"name":"enabled","reason":"invalid_type"}]}},
                                "notesTooLong": {"value": {"ok": False, "error": "invalid", "message": "validation_error", "invalid_params": [{"name":"notes","reason":"max_length_exceeded","max":500}]}}
                            }}}
                        }
                    }
                }, ["401", "403", "404", "422"])
            },
            "/admin/roles": {
                "get": attach({
                    "tags": ["admin"],
                    "security": [{"BearerAuth": []}],
                    "summary": "List users with roles",
                    "description": "pagination stub — currently ignored by API response. Errors on admin routes use RFC7807 (application/problem+json).",
                    "parameters": [
                        {"name": "q", "in": "query", "required": False, "schema": {"type": "string"}, "description": "Filter by email"},
                        {"name": "page", "in": "query", "required": False, "schema": {"type": "integer", "minimum": 1}},
                        {"name": "size", "in": "query", "required": False, "schema": {"type": "integer", "minimum": 1, "maximum": 100}}
                    ],
                    "responses": {
                        "200": {
                            "description": "Users with roles",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "required": ["items", "total"],
                                        "properties": {
                                            "items": {"type": "array", "items": {"$ref": "#/components/schemas/UserWithRole"}},
                                            "total": {"type": "integer"}
                                        },
                                        "additionalProperties": False
                                    },
                                    "examples": {
                                        "ok": {
                                            "value": {
                                                "items": [
                                                    {"id": "u1", "email": "a@ex", "role": "editor"}
                                                ],
                                                "total": 1
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }, ["401", "403"])
            },
            "/admin/roles/{user_id}": {
                "parameters": [
                    {"name": "user_id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}
                ],
                "patch": attach({
                    "tags": ["admin"],
                    "security": [{"BearerAuth": [], "CsrfToken": []}],
                    "summary": "Update user role",
                    "description": "On change, an audit event (user_update_role) is recorded. Errors on admin routes use RFC7807 (application/problem+json).",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["role"],
                                    "properties": {"role": {"type": "string", "enum": ["admin", "editor", "viewer"]}},
                                    "additionalProperties": False
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {"description": "OK", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/UserWithRole"}, "examples": {"ok": {"value": {"id": "u1", "email": "a@ex", "role": "editor", "updated_at": "2025-01-01T12:00:00+00:00"}}}}}},
                        "404": {"description": "Not found", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}, "examples": {"userMissing": {"value": {"ok": False, "error": "not_found", "message": "user not found"}}}}}},
                        "422": {"description": "Validation error", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}, "examples": {"invalidRole": {"value": {"ok": False, "error": "invalid", "message": "validation_error", "invalid_params": [{"name":"role","reason":"invalid_enum","allowed":["admin","editor","viewer"]}]}}}}}}
                    }
                }, ["401", "403", "404", "422"])
            }
        }
        spec = {
            "openapi": "3.0.3",
            "info": {"title": "Unified Platform API", "version": "0.3.0"},
            "servers": [{"url": "/"}],
            "tags": [
                {"name": "Auth"}, {"name": "Menus"}, {"name": "Features"}, {"name": "System"},
                {"name": "Notes"}, {"name": "Tasks"}, {"name": "admin"}, {"name": "weekview"}
            ],
            "components": {
                "securitySchemes": {
                    "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
                    # Required for mutating admin operations
                    "CsrfToken": {"type": "apiKey", "in": "header", "name": "X-CSRF-Token", "description": "Fetch via GET /csrf"}
                },
                "schemas": {
                    "ProblemDetails": {
                        "type": "object",
                        "required": ["type","title","status"],
                        "properties": {
                            "type": {"type": "string", "example": "about:blank"},
                            "title": {"type": "string", "example": "Validation error"},
                            "status": {"type": "integer", "example": 422},
                            "detail": {"type": "string", "nullable": True},
                            "request_id": {"type": "string", "nullable": True},
                            "invalid_params": {"type": "array", "items": {"type": "object"}},
                            "required_role": {"type": "string", "nullable": True}
                        },
                        "additionalProperties": True
                    },
                    "Error": error_schema,
                    # Minimal admin-related models
                    "User": {
                        "type": "object",
                        "required": ["id", "email", "role"],
                        "properties": {
                            "id": {"type": "string", "format": "uuid"},
                            "email": {"type": "string", "format": "email"},
                            "role": {"type": "string", "enum": ["admin", "editor", "viewer"]}
                        },
                        "additionalProperties": False
                    },
                    "UserWithRole": {"$ref": "#/components/schemas/User"},
                    "FeatureFlag": {
                        "type": "object",
                        "required": ["key", "enabled"],
                        "properties": {
                            "key": {"type": "string"},
                            "enabled": {"type": "boolean"},
                            "notes": {"type": "string", "nullable": True},
                            "updated_at": {"type": "string", "format": "date-time", "nullable": True}
                        },
                        "additionalProperties": False
                    },
                    "PageMeta": {"type": "object", "required": ["page","size","total","pages"], "properties": {"page": {"type": "integer"}, "size": {"type": "integer"}, "total": {"type": "integer"}, "pages": {"type": "integer"}}},
                    "PageResponse_Notes": {"type": "object", "required": ["ok","items","meta"], "properties": {"ok": {"type": "boolean"}, "items": {"type": "array", "items": {"$ref": "#/components/schemas/Note"}}, "meta": {"$ref": "#/components/schemas/PageMeta"}}},
                    "PageResponse_Tasks": {"type": "object", "required": ["ok","items","meta"], "properties": {"ok": {"type": "boolean"}, "items": {"type": "array", "items": {"$ref": "#/components/schemas/Task"}}, "meta": {"$ref": "#/components/schemas/PageMeta"}}},
                    "LimitView": {"type": "object", "required": ["name","quota","per_seconds","source"], "properties": {"name": {"type": "string"}, "quota": {"type": "integer"}, "per_seconds": {"type": "integer"}, "source": {"type": "string", "enum": ["tenant","default","fallback"]}, "tenant_id": {"type": "integer", "nullable": True}}},
                    "PageResponse_LimitView": {"type": "object", "required": ["ok","items","meta"], "properties": {"ok": {"type": "boolean"}, "items": {"type": "array", "items": {"$ref": "#/components/schemas/LimitView"}}, "meta": {"$ref": "#/components/schemas/PageMeta"}}},
                    "LimitUpsertRequest": {"type": "object", "required": ["tenant_id","name","quota","per_seconds"], "properties": {"tenant_id": {"type": "integer"}, "name": {"type": "string"}, "quota": {"type": "integer"}, "per_seconds": {"type": "integer"}}},
                    "LimitDeleteRequest": {"type": "object", "required": ["tenant_id","name"], "properties": {"tenant_id": {"type": "integer"}, "name": {"type": "string"}}},
                    "LimitMutationResponse": {"type": "object", "required": ["ok"], "properties": {"ok": {"type": "boolean"}, "item": {"$ref": "#/components/schemas/LimitView"}, "updated": {"type": "boolean"}, "removed": {"type": "boolean"}}},
                    "ImportRow": {"type": "object", "required": ["title","description","priority"], "properties": {"title": {"type": "string"}, "description": {"type": "string"}, "priority": {"type": "integer"}}},
                    "ImportOkResponse": {"type": "object", "required": ["ok","rows","meta"], "properties": {"ok": {"type": "boolean", "enum": [True]}, "rows": {"type": "array", "items": {"$ref": "#/components/schemas/ImportRow"}}, "meta": {"type": "object", "required": ["count"], "properties": {"count": {"type": "integer"}, "dry_run": {"type": "boolean", "description": "Present and true when request used ?dry_run=1"}, "format": {"type": "string", "enum": ["csv","docx","xlsx","menu"], "description": "Detected import format"}}, "additionalProperties": False}, "dry_run": {"type": "boolean", "description": "Legacy alias (deprecated); prefer meta.dry_run"}, "diff": {"type": "array", "items": {"type": "object"}, "description": "Menu dry-run diff entries (menu only)"}}, "additionalProperties": False},
                    "ImportErrorResponse": {"type": "object", "required": ["ok","error","message"], "properties": {"ok": {"type": "boolean", "enum": [False]}, "error": {"type": "string", "enum": ["invalid","unsupported","rate_limited"]}, "message": {"type": "string"}, "retry_after": {"type": "integer","nullable": True}, "limit": {"type": "string","nullable": True}}},
                    "ImportMenuRequest": {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}}}}},
                    "Note": note_schema,
                    "NoteCreate": {"type": "object", "required": ["content"], "properties": {"content": {"type": "string"}, "private_flag": {"type": "boolean"}}},
                    "Task": task_schema,
                    "TaskCreate": {"type": "object", "required": ["title"], "properties": {"title": {"type": "string"}, "task_type": {"type": "string"}, "private_flag": {"type": "boolean"}, "status": {"$ref": "#/components/schemas/TaskStatus"}}},
                    "TaskStatus": {"type": "string", "enum": ["todo","doing","blocked","done","cancelled"]},
                    "TenantSummary": {"type": "object", "required": ["id","name","active","features"], "properties": {"id": {"type":"integer"}, "name": {"type":"string"}, "active": {"type":"boolean"}, "features": {"type":"array", "items": {"type":"string"}}, "kind": {"type":"string","nullable":True}, "description": {"type":"string","nullable":True}}},
                    "TenantListResponse": {"type": "object", "required": ["ok","tenants"], "properties": {"ok": {"type":"boolean"}, "tenants": {"type":"array", "items": {"$ref": "#/components/schemas/TenantSummary"}}}},
                    "AuditView": {"type": "object", "properties": {"id": {"type": "integer"}, "ts": {"type": "string", "format": "date-time"}, "tenant_id": {"type": "integer", "nullable": True}, "actor_user_id": {"type": "integer", "nullable": True}, "actor_role": {"type": "string"}, "event": {"type": "string"}, "payload": {"type": "object", "additionalProperties": True}, "request_id": {"type": "string"}}},
                    "PageResponse_AuditView": {"type": "object", "required": ["ok","items","meta"], "properties": {"ok": {"type": "boolean"}, "items": {"type": "array", "items": {"$ref": "#/components/schemas/AuditView"}}, "meta": {"$ref": "#/components/schemas/PageMeta"}}},
                },
                "headers": {
                    "X-Request-Id": {
                        "description": "Echoed from request or generated by server; useful for log correlation.",
                        "schema": {"type": "string"},
                        "example": "f3a2b1f8-2e0e-4b12-9f4c-5c28a6a0c3a1"
                    }
                },
                "responses": reusable,
            },
            "paths": paths,
        }
        # Standard 415 component (Unsupported Media Type)
        spec.setdefault("components", {}).setdefault("responses", {})["UnsupportedMediaType"] = {
            "description": "Unsupported Media Type"
        }
        # Inject Import API paths
        spec["paths"]["/import/csv"] = {
            "post": {
                "summary": "Import CSV file",
                "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {"type": "object", "required": ["file"], "properties": {"file": {"type": "string", "format": "binary"}}}}}},
                "responses": {
                    "200": {"description": "OK", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ImportOkResponse"}}}},
                    "400": {"description": "Invalid", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ImportErrorResponse"}}}},
                    "415": {"$ref": "#/components/responses/UnsupportedMediaType"},
                    "429": {"description": "Rate limited", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ImportErrorResponse"}}}},
                },
            }
        }
        spec["paths"]["/import/docx"] = {
            "post": {
                "summary": "Import DOCX table",
                "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {"type": "object", "required": ["file"], "properties": {"file": {"type": "string", "format": "binary"}}}}}},
                "responses": {
                    "200": {"description": "OK", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ImportOkResponse"}}}},
                    "400": {"description": "Invalid", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ImportErrorResponse"}}}},
                    "415": {"$ref": "#/components/responses/UnsupportedMediaType"},
                    "429": {"description": "Rate limited", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ImportErrorResponse"}}}},
                },
            }
        }
        spec["paths"]["/import/xlsx"] = {
            "post": {
                "summary": "Import XLSX spreadsheet",
                "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {"type": "object", "required": ["file"], "properties": {"file": {"type": "string", "format": "binary"}}}}}},
                "responses": {
                    "200": {"description": "OK", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ImportOkResponse"}}}},
                    "400": {"description": "Invalid", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ImportErrorResponse"}}}},
                    "415": {"$ref": "#/components/responses/UnsupportedMediaType"},
                    "429": {"description": "Rate limited", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ImportErrorResponse"}}}},
                },
            }
        }
        spec["paths"]["/import/menu"] = {
            "post": {
                "summary": "Import weekly menu (dry-run supported)",
                "parameters": [
                    {"name": "dry_run", "in": "query", "required": False, "schema": {"type": "boolean", "default": False}, "description": "If true (1) perform validation + diff only (no persistence)"}
                ],
                "requestBody": {"required": True, "content": {
                    "multipart/form-data": {"schema": {"type": "object", "required": ["file"], "properties": {"file": {"type": "string", "format": "binary"}}}},
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ImportMenuRequest"},
                        "examples": {
                            "minimal": {
                                "summary": "Minimal valid payload",
                                "value": {"items": [{"name": "Spaghetti Bolognese"}]}
                            }
                        }
                    }
                }},
                "responses": {
                    "200": {"description": "OK", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ImportOkResponse"}, "examples": {"dryRun": {"value": {"ok": True, "rows": [{"title": "Soup", "description": "Tomato", "priority": 1}], "meta": {"count": 1, "dry_run": True, "format": "menu"}, "dry_run": True}}}}}},
                    "400": {"description": "Invalid", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ImportErrorResponse"}}}},
                    "415": {"$ref": "#/components/responses/UnsupportedMediaType"},
                    "429": {"description": "Rate limited", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ImportErrorResponse"}}}},
                },
            }
        }
        # Spec-only stubs, gated by OPENAPI_INCLUDE_PARTS (default on)
        include_parts = os.environ.get("OPENAPI_INCLUDE_PARTS", "1")
        if include_parts != "0":
            # Minimal admin schema
            spec.setdefault("components", {}).setdefault("schemas", {})["AdminStats"] = {
                "type": "object",
                "description": "Aggregate admin statistics",
                "additionalProperties": True
            }
            # Admin stats stub
            spec["paths"]["/api/admin/stats"] = {
                "get": {
                    "tags": ["admin"],
                    "summary": "Admin stats",
                    "responses": {
                        "200": {"description": "OK"}
                    },
                }
            }
            # Weekview stubs
            spec["paths"]["/api/weekview"] = {
                "get": {
                    "tags": ["weekview"],
                    "summary": "Weekview overview",
                    "responses": {
                        "200": {"description": "OK"}
                    },
                }
            }
            spec["paths"]["/api/weekview/resolve"] = {
                "get": {
                    "tags": ["weekview"],
                    "summary": "Weekview resolve",
                    "responses": {
                        "200": {"description": "OK"}
                    },
                }
            }
        return spec

    # --- Feature flag management endpoints (regression restore) ---
    from .rate_limit import RateLimitExceeded, allow, rate_limited_response

    @app.get("/features")
    @require_roles("admin")
    def list_features():  # pragma: no cover
        tid = getattr(g, "tenant_id", None)
        try:
            allow(tid, session.get("user_id"), "feature_flags_admin", 30, testing=app.config.get("TESTING", False))
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
    def check_feature():  # pragma: no cover
        name = (request.args.get("name") or "").strip()
        if not name:
            return jsonify({"ok": False, "error": "name required"}), 400
        tid = getattr(g, "tenant_id", None)
        if tid is None:
            return jsonify({"ok": False, "error": "tenant required"}), 400
        try:
            allow(tid, session.get("user_id"), "feature_flags_admin", 60, testing=app.config.get("TESTING", False))
        except RateLimitExceeded:
            return rate_limited_response()
        db = get_session()
        try:
            rec = db.query(TenantFeatureFlag.enabled).filter(TenantFeatureFlag.tenant_id == tid, TenantFeatureFlag.name == name).first()
            if rec is not None:
                return {"ok": True, "name": name, "enabled": bool(rec[0])}
            return {"ok": True, "name": name, "enabled": False}
        finally:
            db.close()

    @app.post("/features/set")
    @require_roles("admin")
    def set_feature():  # pragma: no cover
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
            allow(tid, session.get("user_id"), "feature_flags_admin", 20, testing=app.config.get("TESTING", False))
        except RateLimitExceeded:
            return rate_limited_response()
        db = get_session()
        try:
            rec = db.query(TenantFeatureFlag).filter(TenantFeatureFlag.tenant_id == tid, TenantFeatureFlag.name == name).first()
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

    # --- Bootstrap superuser if env provides credentials (skip under TESTING) ---
    if not app.config.get("TESTING", False):
        with app.app_context():  # pragma: no cover (simple bootstrap)
            ensure_bootstrap_superuser()

    # --- Guard test endpoints (P6.2) ---
    @app.get("/_guard/editor")
    @require_roles("editor")
    def _guard_editor():  # pragma: no cover - exercised in dedicated tests
        return {"ok": True, "guard": "editor"}

    @app.get("/_guard/admin")
    @require_roles("admin")
    def _guard_admin():  # pragma: no cover - exercised in dedicated tests
        return {"ok": True, "guard": "admin"}

    # --- Test / demonstration rate limit endpoint (Pocket 7) ---
    try:
        from .http_limits import limit

        @app.get("/_limit/test")
        @limit("test_endpoint", quota=3, per_seconds=60)
        def _limit_test():  # pragma: no cover - will be covered in new rate limit tests
            return {"ok": True, "limited": False}
    except Exception:  # pragma: no cover
        pass

    return app
