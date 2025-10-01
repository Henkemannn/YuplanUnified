from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, TypedDict

# Lightweight JWT HS256 implementation without external deps.

class JWTError(Exception):
    pass

DEFAULT_ACCESS_TTL = 600  # 10 min
DEFAULT_REFRESH_TTL = 1209600  # 14 days
SKEW_SECS = 30

ALG = "HS256"

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)

def _sign(msg: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode(), msg, hashlib.sha256).digest()
    return _b64url(sig)

def generate_jti() -> str:
    return secrets.token_hex(16)


def encode(payload: dict[str, Any], *, secret: str, ttl: int) -> str:
    now = int(time.time())
    header = {"alg": ALG, "typ": "JWT"}
    pl = payload.copy()
    pl.setdefault("iat", now)
    pl.setdefault("exp", now + ttl)
    header_b = _b64url(json.dumps(header, separators=(",",":")).encode())
    payload_b = _b64url(json.dumps(pl, separators=(",",":")).encode())
    msg = f"{header_b}.{payload_b}".encode()
    sig = _sign(msg, secret)
    return f"{header_b}.{payload_b}.{sig}"


class DecodedToken(TypedDict, total=False):
    sub: int | str
    role: str
    tenant_id: int | str
    jti: str
    type: str  # access|refresh
    iat: int
    exp: int
    nbf: int


def decode(token: str, *, secret: str, verify_exp: bool = True) -> DecodedToken:
    try:
        header_b, payload_b, sig = token.split(".")
    except ValueError as e:
        raise JWTError("malformed token") from e
    msg = f"{header_b}.{payload_b}".encode()
    expected = _sign(msg, secret)
    if not hmac.compare_digest(expected, sig):
        raise JWTError("bad signature")
    try:
        raw = json.loads(_b64url_decode(payload_b))
        # Enforce dict type
        if not isinstance(raw, dict):  # pragma: no cover defensive
            raise JWTError("bad payload type")
        payload: DecodedToken = raw  # type: ignore[assignment]
    except Exception as e:
        raise JWTError("bad payload") from e
    if verify_exp:
        now = int(time.time())
        exp = int(payload.get("exp", 0))
        if now > exp + SKEW_SECS:
            raise JWTError("token expired")
        nbf = payload.get("nbf")
        if nbf and now + SKEW_SECS < int(nbf):
            raise JWTError("token not yet valid")
    return payload


def issue_token_pair(*, user_id: int, role: str, tenant_id: int, secret: str, access_ttl: int = DEFAULT_ACCESS_TTL, refresh_ttl: int = DEFAULT_REFRESH_TTL) -> tuple[str,str,str]:
    jti = generate_jti()
    access = encode({"sub": user_id, "role": role, "tenant_id": tenant_id, "jti": generate_jti(), "type": "access"}, secret=secret, ttl=access_ttl)
    refresh = encode({"sub": user_id, "role": role, "tenant_id": tenant_id, "jti": jti, "type": "refresh"}, secret=secret, ttl=refresh_ttl)
    return access, refresh, jti
