"""User management repository for admin panel"""

from __future__ import annotations

import secrets
from typing import Optional

from sqlalchemy import text
from werkzeug.security import generate_password_hash

from .db import get_session
from .models import User


def _normalize_email(email: Optional[str]) -> str:
    return str(email or "").strip().lower()


def _users_table_has_site_id(db) -> bool:
    try:
        cols = db.execute(text("PRAGMA table_info(users)")).fetchall()
        return any(str(col[1]) == "site_id" for col in cols)
    except Exception:
        return False


def _kitchen_site_binding_table_exists(db) -> bool:
    try:
        row = db.execute(
            text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='kitchen_user_sites' LIMIT 1")
        ).fetchone()
        return row is not None
    except Exception:
        return False


def _resolve_user_site_id(db, user_id: int, tenant_id: int | None = None) -> str | None:
    if _users_table_has_site_id(db):
        row = db.execute(text("SELECT site_id FROM users WHERE id=:uid LIMIT 1"), {"uid": int(user_id)}).fetchone()
        site_id = str(row[0]).strip() if row and row[0] is not None else ""
        if site_id:
            return site_id
    if _kitchen_site_binding_table_exists(db):
        params = {"uid": int(user_id)}
        query = "SELECT site_id FROM kitchen_user_sites WHERE user_id=:uid"
        if tenant_id is not None:
            query += " AND tenant_id=:tid"
            params["tid"] = int(tenant_id)
        row = db.execute(text(query + " LIMIT 1"), params).fetchone()
        site_id = str(row[0]).strip() if row and row[0] is not None else ""
        if site_id:
            return site_id
    return None


def _set_user_site_binding(db, *, user_id: int, tenant_id: int, site_id: str) -> None:
    if _users_table_has_site_id(db):
        db.execute(
            text("UPDATE users SET site_id=:sid WHERE id=:uid AND tenant_id=:tid"),
            {"sid": str(site_id), "uid": int(user_id), "tid": int(tenant_id)},
        )
        return
    db.execute(
        text(
            "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
            "user_id INTEGER PRIMARY KEY, "
            "tenant_id INTEGER NOT NULL, "
            "site_id TEXT NOT NULL"
            ")"
        )
    )
    db.execute(
        text(
            "INSERT INTO kitchen_user_sites (user_id, tenant_id, site_id) "
            "VALUES (:uid, :tid, :sid) "
            "ON CONFLICT(user_id) DO UPDATE SET tenant_id=excluded.tenant_id, site_id=excluded.site_id"
        ),
        {"uid": int(user_id), "tid": int(tenant_id), "sid": str(site_id)},
    )


class AdminUserRepo:
    """Repository for user CRUD operations in admin panel"""

    def list_users_for_tenant(self, tenant_id: int) -> list[dict]:
        """
        List all users for a given tenant.
        Returns list of dicts with user info.
        """
        db = get_session()
        try:
            # Query aligned columns from unified schema
            rows = db.execute(
                text(
                    "SELECT u.id, u.username, u.email, u.full_name, u.role, u.is_active, u.department_id, d.name, s.name, u.must_change_password "
                    "FROM users u "
                    "LEFT JOIN departments d ON d.id = u.department_id "
                    "LEFT JOIN sites s ON s.id = d.site_id "
                    "WHERE u.tenant_id = :tid "
                    "ORDER BY u.username, u.email"
                ),
                {"tid": tenant_id}
            ).fetchall()
            
            users = []
            for row in rows:
                site_id = _resolve_user_site_id(db, int(row[0]), tenant_id=tenant_id)
                site_name = str(row[8] or "").strip()
                if not site_name and site_id:
                    site_row = db.execute(
                        text("SELECT name FROM sites WHERE id=:sid AND tenant_id=:tid LIMIT 1"),
                        {"sid": site_id, "tid": int(tenant_id)},
                    ).fetchone()
                    site_name = str(site_row[0] or "").strip() if site_row else ""
                users.append({
                    "id": row[0],
                    "username": row[1],
                    "email": row[2],
                    "full_name": row[3],
                    "role": row[4],
                    "is_active": bool(row[5]) if row[5] is not None else True,
                    "department_id": row[6],
                    "department_name": row[7],
                    "site_name": site_name,
                    "site_id": site_id,
                    "must_change_password": bool(row[9]) if row[9] is not None else False,
                })
            return users
        finally:
            db.close()

    def get_user(self, user_id: int) -> Optional[dict]:
        """Get a single user by ID"""
        db = get_session()
        try:
            row = db.execute(
                text(
                    "SELECT u.id, u.username, u.email, u.full_name, u.role, u.is_active, u.tenant_id, u.department_id, d.name, s.name, u.must_change_password "
                    "FROM users u "
                    "LEFT JOIN departments d ON d.id = u.department_id "
                    "LEFT JOIN sites s ON s.id = d.site_id "
                    "WHERE u.id = :uid"
                ),
                {"uid": user_id}
            ).fetchone()
            
            
            if not row:
                return None

            site_id = _resolve_user_site_id(db, int(row[0]), tenant_id=int(row[6]) if row[6] is not None else None)
            site_name = str(row[9] or "").strip()
            if not site_name and site_id and row[6] is not None:
                site_row = db.execute(
                    text("SELECT name FROM sites WHERE id=:sid AND tenant_id=:tid LIMIT 1"),
                    {"sid": site_id, "tid": int(row[6])},
                ).fetchone()
                site_name = str(site_row[0] or "").strip() if site_row else ""
            
            return {
                "id": row[0],
                "username": row[1],
                "email": row[2],
                "full_name": row[3],
                "role": row[4],
                "is_active": bool(row[5]),
                "tenant_id": row[6],
                "department_id": row[7],
                "department_name": row[8],
                "site_name": site_name,
                "site_id": site_id,
                "must_change_password": bool(row[10]) if len(row) > 10 and row[10] is not None else False,
            }
        finally:
            db.close()

    def create_user(
        self, 
        tenant_id: int,
        username: str,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        role: str = "staff",
        is_active: bool = True,
        department_id: Optional[str] = None,
    ) -> int:
        """
        Create a new user.
        Returns the new user ID.
        """
        password_hash = generate_password_hash(password)
        normalized_email = _normalize_email(email)
        
        db = get_session()
        try:
            # Use ORM for creation
            user = User(
                tenant_id=tenant_id,
                username=username,
                email=normalized_email,
                password_hash=password_hash,
                full_name=full_name,
                role=role,
                is_active=is_active,
                department_id=department_id,
                must_change_password=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return user.id
        finally:
            db.close()

    def update_user(
        self,
        user_id: int,
        email: Optional[str] = None,
        full_name: Optional[str] = None,
        role: Optional[str] = None
        ,
        department_id: Optional[str] = None
    ) -> bool:
        """
        Update user fields.
        Returns True if successful.
        """
        db = get_session()
        try:
            # Build dynamic update
            updates = []
            params = {"uid": user_id}
            
            if email is not None:
                updates.append("email = :email")
                params["email"] = _normalize_email(email)
            
            if full_name is not None:
                updates.append("full_name = :full_name")
                params["full_name"] = full_name
            
            if role is not None:
                updates.append("role = :role")
                params["role"] = role

            if department_id is not None:
                updates.append("department_id = :department_id")
                params["department_id"] = department_id
            
            if not updates:
                return True  # Nothing to update
            
            sql = f"UPDATE users SET {', '.join(updates)} WHERE id = :uid"
            result = db.execute(text(sql), params)
            db.commit()
            
            return result.rowcount > 0
        finally:
            db.close()

    def deactivate_user(self, user_id: int) -> bool:
        """
        Soft-delete: mark user as inactive.
        Returns True if successful.
        """
        db = get_session()
        try:
            result = db.execute(
                text("UPDATE users SET is_active = 0 WHERE id = :uid"),
                {"uid": user_id}
            )
            db.commit()
            return result.rowcount > 0
        finally:
            db.close()

    def activate_user(self, user_id: int) -> bool:
        """Reactivate a user"""
        db = get_session()
        try:
            result = db.execute(
                text("UPDATE users SET is_active = 1 WHERE id = :uid"),
                {"uid": user_id}
            )
            db.commit()
            return result.rowcount > 0
        finally:
            db.close()

    def reset_password(self, user_id: int) -> str:
        """
        Generate a temporary password for a user.
        Returns the plaintext password (for display to admin).
        """
        # Generate 12-character password
        temp_password = secrets.token_urlsafe(9)  # ~12 chars base64
        password_hash = generate_password_hash(temp_password)
        
        db = get_session()
        try:
            db.execute(
                text(
                    "UPDATE users "
                    "SET password_hash = :ph, auth_version = COALESCE(auth_version, 1) + 1, refresh_token_jti = NULL, must_change_password = 1 "
                    "WHERE id = :uid"
                ),
                {"ph": password_hash, "uid": user_id},
            )
            db.commit()
            return temp_password
        finally:
            db.close()

    def set_site_binding(self, user_id: int, tenant_id: int, site_id: str) -> None:
        db = get_session()
        try:
            _set_user_site_binding(db, user_id=user_id, tenant_id=tenant_id, site_id=site_id)
            db.commit()
        finally:
            db.close()

    def username_exists(self, username: str, exclude_user_id: Optional[int] = None) -> bool:
        """Check if username already exists"""
        db = get_session()
        try:
            if exclude_user_id:
                row = db.execute(
                    text("SELECT 1 FROM users WHERE username = :u AND id != :eid LIMIT 1"),
                    {"u": username, "eid": exclude_user_id}
                ).fetchone()
            else:
                row = db.execute(
                    text("SELECT 1 FROM users WHERE username = :u LIMIT 1"),
                    {"u": username}
                ).fetchone()
            return row is not None
        finally:
            db.close()

    def email_exists(self, email: str, exclude_user_id: Optional[int] = None) -> bool:
        """Check if email already exists"""
        normalized_email = _normalize_email(email)
        if not normalized_email:
            return False
        db = get_session()
        try:
            if exclude_user_id:
                row = db.execute(
                    text("SELECT 1 FROM users WHERE lower(email) = :e AND id != :eid LIMIT 1"),
                    {"e": normalized_email, "eid": exclude_user_id}
                ).fetchone()
            else:
                row = db.execute(
                    text("SELECT 1 FROM users WHERE lower(email) = :e LIMIT 1"),
                    {"e": normalized_email}
                ).fetchone()
            return row is not None
        finally:
            db.close()
