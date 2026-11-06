from __future__ import annotations

import uuid

import pytest
from core.admin_user_repo import AdminUserRepo
from core.app_factory import create_app
from core.db import create_all, get_session
from core.models import Tenant, User
from core.password_policy import PasswordPolicyError, validate_new_password
from werkzeug.security import check_password_hash, generate_password_hash


@pytest.mark.parametrize(
    "password",
    [
        "short-password",
        "password123456789",
        "123456789012345",
    ],
)
def test_password_policy_rejects_short_or_compromised_values(password):
    with pytest.raises(PasswordPolicyError):
        validate_new_password(password)


def test_password_policy_accepts_unicode_spaces_and_at_least_64_characters():
    password = "  Ängsblomma café " + ("安全" * 24)
    assert len(password) >= 64
    validate_new_password(password)


def test_password_policy_supports_deployment_blocklist_extension(monkeypatch):
    monkeypatch.setenv("YUPLAN_PASSWORD_BLOCKLIST", "OrganisationensHemlighet")
    with pytest.raises(PasswordPolicyError):
        validate_new_password("OrganisationensHemlighet")


def test_admin_generated_temporary_password_is_long_and_forces_change(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "database_url": f"sqlite:///{(tmp_path / 'admin-reset.db').as_posix()}",
            "FORCE_DB_REINIT": True,
        }
    )
    with app.app_context():
        create_all()
        db = get_session()
        tenant = Tenant(name=f"Policy tenant {uuid.uuid4().hex}")
        db.add(tenant)
        db.flush()
        user = User(
            tenant_id=tenant.id,
            email="admin-reset@example.test",
            password_hash=generate_password_hash("old-password"),
            role="admin",
            must_change_password=False,
        )
        db.add(user)
        db.commit()
        user_id = user.id
        temporary_password = AdminUserRepo().reset_password(user_id)
        db.expire_all()
        refreshed = db.get(User, user_id)
        assert refreshed is not None
        assert len(temporary_password) >= 15
        assert refreshed.must_change_password is True
        assert check_password_hash(refreshed.password_hash, temporary_password)
        db.close()


def test_admin_and_kitchen_user_creation_use_the_shared_policy(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "database_url": f"sqlite:///{(tmp_path / 'user-creation.db').as_posix()}",
            "FORCE_DB_REINIT": True,
        }
    )
    with app.app_context():
        create_all()
        db = get_session()
        tenant = Tenant(name=f"Creation tenant {uuid.uuid4().hex}")
        db.add(tenant)
        db.commit()
        tenant_id = int(tenant.id)
        repo = AdminUserRepo()
        valid_password = "A long valid password 2026"
        admin_id = repo.create_user(
            tenant_id=tenant_id,
            username="created-admin@example.test",
            email="created-admin@example.test",
            password=valid_password,
            role="admin",
        )
        kitchen_id = repo.create_user(
            tenant_id=tenant_id,
            username="created-kitchen@example.test",
            email="created-kitchen@example.test",
            password=valid_password,
            role="kitchen",
        )
        assert db.get(User, admin_id).role == "admin"
        assert db.get(User, kitchen_id).role == "kitchen"
        before = db.query(User).count()
        with pytest.raises(PasswordPolicyError):
            repo.create_user(
                tenant_id=tenant_id,
                username="rejected@example.test",
                email="rejected@example.test",
                password="too-short",
                role="admin",
            )
        assert db.query(User).count() == before
        db.close()
