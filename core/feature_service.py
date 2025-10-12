from __future__ import annotations

from collections.abc import Sequence

from werkzeug.security import generate_password_hash

from .db import get_session
from .models import Tenant, TenantFeatureFlag, User

MODULE_FEATURE_MAP = {
    "municipal": ["module.municipal", "menus", "diet", "attendance"],
    "offshore": [
        "module.offshore",
        "menus",
        "attendance",
        "turnus",
        "waste.metrics",
        "prep.tasks",
        "freezer.tasks",
        "messaging",
    ],
}


class FeatureService:
    def list(self, tenant_id: int) -> list[str]:
        db = get_session()
        try:
            rows = db.query(TenantFeatureFlag).filter_by(tenant_id=tenant_id, enabled=True).all()
            return [r.name for r in rows]
        finally:
            db.close()

    def enable(self, tenant_id: int, name: str):
        db = get_session()
        try:
            row = db.query(TenantFeatureFlag).filter_by(tenant_id=tenant_id, name=name).first()
            if row:
                row.enabled = True
            else:
                row = TenantFeatureFlag(tenant_id=tenant_id, name=name, enabled=True)
                db.add(row)
            db.commit()
        finally:
            db.close()

    def disable(self, tenant_id: int, name: str):
        db = get_session()
        try:
            row = db.query(TenantFeatureFlag).filter_by(tenant_id=tenant_id, name=name).first()
            if row:
                row.enabled = False
                db.commit()
        finally:
            db.close()

    def seed_modules(self, tenant_id: int, modules: Sequence[str]):
        for m in modules:
            feats = MODULE_FEATURE_MAP.get(m, [])
            for f in feats:
                self.enable(tenant_id, f)

    def create_tenant_with_admin(
        self, name: str, modules: Sequence[str], admin_email: str, admin_password: str
    ) -> int:
        db = get_session()
        try:
            tenant = Tenant(name=name)
            db.add(tenant)
            db.flush()
            # Seed features
            for m in modules:
                feats = MODULE_FEATURE_MAP.get(m, [])
                for f in feats:
                    db.add(TenantFeatureFlag(tenant_id=tenant.id, name=f, enabled=True))
            # Create admin user
            pw_hash = generate_password_hash(admin_password)
            user = User(
                tenant_id=tenant.id,
                email=admin_email.lower(),
                password_hash=pw_hash,
                role="admin",
                unit_id=None,
            )
            db.add(user)
            db.commit()
            return tenant.id
        finally:
            db.close()
