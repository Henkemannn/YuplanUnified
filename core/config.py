from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Config:
    secret_key: str = "change-me"
    database_url: str = "sqlite:///dev.db"
    default_enabled_modules: list[str] = field(default_factory=lambda: ["municipal"])  # order matters for overrides

    @classmethod
    def from_env(cls) -> Config:
        mods = os.getenv("DEFAULT_ENABLED_MODULES", "municipal")
        return cls(
            secret_key=os.getenv("SECRET_KEY", "change-me"),
            database_url=os.getenv("DATABASE_URL", "sqlite:///dev.db"),
            default_enabled_modules=[m.strip() for m in mods.split(",") if m.strip()],
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
        }
