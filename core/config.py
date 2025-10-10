from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Config:
    secret_key: str = "change-me"
    database_url: str = "sqlite:///dev.db"
    default_enabled_modules: list[str] = field(default_factory=lambda: ["municipal"])  # order matters for overrides
    cors_allowed_origins: list[str] = field(default_factory=list)
    jwt_secrets: list[str] = field(default_factory=list)  # first element used for signing; all accepted for verification
    jwt_issuer: str = "yuplan"
    jwt_audience: str = "api"
    jwt_max_age_seconds: int = 43200  # 12h
    jwt_leeway_seconds: int = 60
    impersonation_max_age_seconds: int = 900  # 15 minutes default
    strict_csrf_env: bool = False
    problem_only: bool = True  # deprecated by ADR-003 (kept for backward compat, unused)

    @classmethod
    def from_env(cls) -> Config:
        mods = os.getenv("DEFAULT_ENABLED_MODULES", "municipal")
        cors = os.getenv("CORS_ALLOW_ORIGINS", "")
        jwt_multi = os.getenv("JWT_SECRETS", "")
        # JWT_SECRETS allows key rotation: comma-separated secrets; first used for signing.
        jwt_list = [s for s in [j.strip() for j in jwt_multi.split(",")] if s]
        return cls(
            secret_key=os.getenv("SECRET_KEY", "change-me"),
            database_url=os.getenv("DATABASE_URL", "sqlite:///dev.db"),
            default_enabled_modules=[m.strip() for m in mods.split(",") if m.strip()],
            cors_allowed_origins=[o for o in [c.strip() for c in cors.split(",")] if o],
            jwt_secrets=jwt_list,
            jwt_issuer=os.getenv("JWT_ISSUER", "yuplan"),
            jwt_audience=os.getenv("JWT_AUDIENCE", "api"),
            jwt_max_age_seconds=int(os.getenv("JWT_MAX_AGE_SECONDS", "43200")),
            jwt_leeway_seconds=int(os.getenv("JWT_LEEWAY_SECONDS", "60")),
            impersonation_max_age_seconds=int(os.getenv("IMPERSONATION_MAX_AGE_SECONDS", "900")),
            strict_csrf_env=bool(int(os.getenv("YUPLAN_STRICT_CSRF", "0"))),
            problem_only=True,
        )

    def override(self, d: dict):
        for k, v in d.items():
            if hasattr(self, k):
                setattr(self, k, v)

    def to_flask_dict(self):
        return {
            "SECRET_KEY": self.secret_key,
            "SQLALCHEMY_DATABASE_URI": self.database_url,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            # Security related derived config
            "CORS_ALLOWED_ORIGINS": self.cors_allowed_origins,
            "JWT_SECRETS": self.jwt_secrets,
            "JWT_ISSUER": self.jwt_issuer,
            "JWT_AUDIENCE": self.jwt_audience,
            "JWT_MAX_AGE_SECONDS": self.jwt_max_age_seconds,
            "JWT_LEEWAY_SECONDS": self.jwt_leeway_seconds,
            "IMPERSONATION_MAX_AGE_SECONDS": self.impersonation_max_age_seconds,
            "YUPLAN_STRICT_CSRF": self.strict_csrf_env,
            # ProblemDetails is always on; legacy flag removed (ADR-003)
            "STRICT_CSRF_IN_TESTS": bool(int(os.getenv("STRICT_CSRF_IN_TESTS", "0"))),
            # Harden session cookie defaults (still allow override in tests)
            "SESSION_COOKIE_HTTPONLY": True,
            "SESSION_COOKIE_SAMESITE": "Lax",
            # SECURE only when not explicitly disabled and not in DEBUG/TESTING
        }
