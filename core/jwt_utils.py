from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Literal, TypedDict

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


Issuer = Literal["yuplan"]

class AccessTokenPayload(TypedDict):
    sub: int
    role: str
    tenant_id: int
    jti: str
    iat: int
    exp: int
    type: Literal["access"]
    iss: Issuer

class RefreshTokenPayload(TypedDict):
    sub: int
    role: str
    tenant_id: int
    jti: str
    iat: int
    exp: int
    type: Literal["refresh"]
    iss: Issuer

DecodedToken = AccessTokenPayload | RefreshTokenPayload


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
    except Exception as e:  # pragma: no cover
        raise JWTError("bad payload") from e
    if not isinstance(raw, dict):  # pragma: no cover defensive
        raise JWTError("bad payload type")
    # Default issuer if absent
    raw.setdefault("iss", "yuplan")
    token_type = raw.get("type")
    if token_type not in ("access", "refresh"):
        raise JWTError("unknown token type")
    # Validate required claims and types
    def _req(key: str, t: type) -> Any:
        if key not in raw:
            raise JWTError(f"missing claim {key}")
        val = raw[key]
        if not isinstance(val, t):
            raise JWTError(f"bad claim type {key}")
        return val
    sub = _req("sub", int)
    role = _req("role", str)
    tenant_id = _req("tenant_id", int)
    jti = _req("jti", str)
    iat = _req("iat", int)
    exp = _req("exp", int)
    iss_val = _req("iss", str)
    nbf_val = raw.get("nbf")
    if nbf_val is not None and not isinstance(nbf_val, int):
        raise JWTError("bad claim type nbf")
    now = int(time.time())
    if verify_exp:
        if now > exp + SKEW_SECS:
            raise JWTError("token expired")
        if nbf_val is not None and now + SKEW_SECS < nbf_val:
            raise JWTError("token not yet valid")
    if token_type == "access":
        return AccessTokenPayload(sub=sub, role=role, tenant_id=tenant_id, jti=jti, iat=iat, exp=exp, iss=iss_val, type="access")
    return RefreshTokenPayload(sub=sub, role=role, tenant_id=tenant_id, jti=jti, iat=iat, exp=exp, iss=iss_val, type="refresh")


def issue_token_pair(*, user_id: int, role: str, tenant_id: int, secret: str, access_ttl: int = DEFAULT_ACCESS_TTL, refresh_ttl: int = DEFAULT_REFRESH_TTL) -> tuple[str, str, str]:
    jti = generate_jti()
    now = int(time.time())
    access_payload: dict[str, Any] = {"sub": user_id, "role": role, "tenant_id": tenant_id, "jti": generate_jti(), "type": "access", "iss": "yuplan", "iat": now, "exp": now + access_ttl}
    refresh_payload: dict[str, Any] = {"sub": user_id, "role": role, "tenant_id": tenant_id, "jti": jti, "type": "refresh", "iss": "yuplan", "iat": now, "exp": now + refresh_ttl}
    access_token = encode(access_payload, secret=secret, ttl=access_ttl)
    refresh_token = encode(refresh_payload, secret=secret, ttl=refresh_ttl)
    return access_token, refresh_token, jti
