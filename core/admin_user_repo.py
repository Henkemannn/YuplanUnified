"""User management repository for admin panel"""

from __future__ import annotations

import secrets
from typing import Optional

from sqlalchemy import text
from werkzeug.security import generate_password_hash
from .ident import canonicalize_identifier

from .db import get_session
from .models import User


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
                    "SELECT id, username, email, full_name, role, is_active "
                    "FROM users "
                    "WHERE tenant_id = :tid "
                    "ORDER BY username, email"
                ),
                {"tid": tenant_id}
            ).fetchall()
            
            users = []
            for row in rows:
                users.append({
                    "id": row[0],
                    "username": row[1],
                    "email": row[2],
                    "full_name": row[3],
                    "role": row[4],
                    "is_active": bool(row[5]) if row[5] is not None else True,
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
                    "SELECT id, username, email, full_name, role, is_active, tenant_id "
                    "FROM users "
                    "WHERE id = :uid"
                ),
                {"uid": user_id}
            ).fetchone()
            
            
            if not row:
                return None
            
            return {
                "id": row[0],
                "username": row[1],
                "email": row[2],
                "full_name": row[3],
                "role": row[4],
                "is_active": bool(row[5]),
                "tenant_id": row[6],
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
        site_id: Optional[str] = None,
    ) -> int:
        """
        Create a new user.
        Returns the new user ID.
        """
        # Canonicalize identity to ensure unicode domains are stored as IDNA
        canon_email = canonicalize_identifier(email or "")
        canon_username = canonicalize_identifier(username or canon_email)
        password_hash = generate_password_hash(password)
        
        db = get_session()
        try:
            # Use ORM for creation
            user = User(
                tenant_id=tenant_id,
                username=canon_username or canon_email,  # ensure non-null username
                email=canon_email,
                password_hash=password_hash,
                full_name=full_name,
                role=role,
                is_active=is_active,
                site_id=site_id if role == "admin" else None,
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
                params["email"] = email
            
            if full_name is not None:
                updates.append("full_name = :full_name")
                params["full_name"] = full_name
            
            if role is not None:
                updates.append("role = :role")
                params["role"] = role
            
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
                text("UPDATE users SET password_hash = :ph WHERE id = :uid"),
                {"ph": password_hash, "uid": user_id}
            )
            db.commit()
            return temp_password
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
        db = get_session()
        try:
            if exclude_user_id:
                row = db.execute(
                    text("SELECT 1 FROM users WHERE email = :e AND id != :eid LIMIT 1"),
                    {"e": email, "eid": exclude_user_id}
                ).fetchone()
            else:
                row = db.execute(
                    text("SELECT 1 FROM users WHERE email = :e LIMIT 1"),
                    {"e": email}
                ).fetchone()
            return row is not None
        finally:
            db.close()
