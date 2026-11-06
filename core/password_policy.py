"""Central policy for user-selected passwords."""

from __future__ import annotations

import os
import unicodedata


MIN_PASSWORD_LENGTH = 15
MAX_PASSWORD_LENGTH = 1024

# Keep this list deliberately small and reviewable. The optional environment
# extension lets deployments add organization-specific compromised values.
COMMON_COMPROMISED_PASSWORDS = frozenset(
    {
        "123456789012345",
        "admin123456789",
        "changeme123456789",
        "correcthorsebatterystaple",
        "iloveyou123456789",
        "letmein123456789",
        "password123456789",
        "qwertyuiop123456",
        "welcome123456789",
    }
)


class PasswordPolicyError(ValueError):
    """Raised when a new password does not satisfy the central policy."""


def _blocked_passwords() -> frozenset[str]:
    configured = os.getenv("YUPLAN_PASSWORD_BLOCKLIST", "")
    configured_values = {
        unicodedata.normalize("NFKC", value).casefold().strip()
        for value in configured.split(",")
        if value.strip()
    }
    return COMMON_COMPROMISED_PASSWORDS | configured_values


def validate_new_password(password: str) -> None:
    """Validate a new user-selected password without altering its contents."""
    if not isinstance(password, str):
        raise PasswordPolicyError("password must be text")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError(
            f"password must be at least {MIN_PASSWORD_LENGTH} characters"
        )
    if len(password) > MAX_PASSWORD_LENGTH:
        raise PasswordPolicyError("password is too long")
    normalized = unicodedata.normalize("NFKC", password).casefold().strip()
    if normalized in _blocked_passwords():
        raise PasswordPolicyError("password is not allowed")
