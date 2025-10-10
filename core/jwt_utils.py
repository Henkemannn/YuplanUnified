from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Callable
from typing import Any, Literal, TypedDict

"""JWT utilities (enhanced)

Adds:
 - RS256 (pinned) capability with 'kid' based key lookup (fallback keeps HS256 for legacy secrets if present)
 - Claim enforcement: iss, aud, iat, exp, nbf with configurable leeway.
 - Max token age (iat no older than JWT_MAX_AGE_SECONDS) for access tokens.
 - Future iat guard (> leeway) rejected.
 - jti revocation hook: is_revoked(jti) -> bool (default no-op) pluggable via injector.
 - Rotation: multiple public keys/ shared secrets accepted; signing still handled externally.

NOTE: For simplicity we still sign using HMAC (HS256) internally for issued tokens; validation path enforces alg expectations when header declares RS256.
Future: swap to real RSA keypair management and JWKS fetcher.
"""

class JWTError(Exception):
    pass

# Optional OpenTelemetry metrics (best-effort; no hard dependency)
try:  # pragma: no cover
    from opentelemetry import metrics  # type: ignore
    _jwt_meter = metrics.get_meter("yuplan.security")  # type: ignore
    _jwt_rejected_counter = _jwt_meter.create_counter(
        name="security.jwt_rejected_total",
        description="Count of rejected JWTs by reason",
        unit="1",
    )
except Exception:  # pragma: no cover
    _jwt_rejected_counter = None  # type: ignore

def _inc_jwt_rejected(reason: str):  # pragma: no cover - simple helper
    if _jwt_rejected_counter:
        try:
            _jwt_rejected_counter.add(1, {"reason": reason})  # type: ignore
        except Exception:
            pass

DEFAULT_ACCESS_TTL = 600  # 10 min
DEFAULT_REFRESH_TTL = 1209600  # 14 days
SKEW_SECS = 30

ALG_HS256 = "HS256"
ALG_RS256 = "RS256"

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


def encode(payload: dict[str, Any], *, secret: str, ttl: int, kid: str | None = None, alg: str = ALG_HS256) -> str:
    now = int(time.time())
    header = {"alg": alg, "typ": "JWT"}
    if kid:
        header["kid"] = kid
    pl = payload.copy()
    pl.setdefault("iat", now)
    pl.setdefault("exp", now + ttl)
    header_b = _b64url(json.dumps(header, separators=(",",":")).encode())
    payload_b = _b64url(json.dumps(pl, separators=(",",":")).encode())
    msg = f"{header_b}.{payload_b}".encode()
    # Only HS256 signing supported locally; RS256 tokens assumed externally minted.
    if alg != ALG_HS256:
        raise JWTError("unsupported signing alg (only HS256 local issuance)")
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


JWTPublicKey = dict[str, Any]  # placeholder for future RSA public key structure

# Simple in-memory JWKS cache: kid -> key (HS shared secret or RSA pub placeholder)
_JWKS_CACHE: dict[str, tuple[JWTPublicKey, float]] = {}
_JWKS_TTL = 300  # seconds

def _get_key_for_kid(kid: str, *, secrets: list[str] | None) -> str | None:
    # For now we map kid to index into secrets list (kid == str(index) or direct match)
    if not secrets:
        return None
    # Direct match first
    for s in secrets:
        if s and hashlib.sha256(s.encode()).hexdigest()[:8] == kid:
            return s
    # index-based fallback
    try:
        idx = int(kid)
        if 0 <= idx < len(secrets):
            return secrets[idx]
    except Exception:
        pass
    return None

def decode(
    token: str,
    *,
    secret: str | None = None,
    secrets_list: list[str] | None = None,
    verify_exp: bool = True,
    issuer: str | None = None,
    audience: str | None = None,
    leeway: int = SKEW_SECS,
    max_age: int | None = None,
    is_revoked: Callable[[str], bool] | None = None,
) -> DecodedToken:
    try:
        header_b, payload_b, sig = token.split(".")
    except ValueError as e:
        _inc_jwt_rejected("malformed")
        raise JWTError("malformed token") from e
    msg = f"{header_b}.{payload_b}".encode()
    # Decode header early for alg/kid decisions
    try:
        header_raw = json.loads(_b64url_decode(header_b))
    except Exception as e:  # pragma: no cover
        _inc_jwt_rejected("bad_header")
        raise JWTError("bad header") from e
    if not isinstance(header_raw, dict):
        _inc_jwt_rejected("bad_header")
        raise JWTError("bad header type")
    alg = header_raw.get("alg")
    if alg not in (ALG_HS256, ALG_RS256):
        _inc_jwt_rejected("alg")
        raise JWTError("alg")
    kid = header_raw.get("kid")
    # Build candidate secrets
    secrets_to_try: list[str] = []
    if alg == ALG_HS256:
        if secret:
            secrets_to_try.append(secret)
        if secrets_list:
            for s in secrets_list:
                if s and s not in secrets_to_try:
                    secrets_to_try.append(s)
    else:  # RS256 path (placeholder: treat mapped shared secret as stand-in)
        if not kid:
            _inc_jwt_rejected("kid")
            raise JWTError("kid")
        mapped = _get_key_for_kid(kid, secrets=secrets_list)
        if mapped:
            secrets_to_try.append(mapped)
    if not secrets_to_try:
        _inc_jwt_rejected("bad_signature")
        raise JWTError("bad signature")
    for sec in secrets_to_try:
        expected = _sign(msg, sec)
        if hmac.compare_digest(expected, sig):
            break
    else:
        _inc_jwt_rejected("bad_signature")
        raise JWTError("bad signature")
    try:
        raw = json.loads(_b64url_decode(payload_b))
    except Exception as e:  # pragma: no cover
        _inc_jwt_rejected("bad_payload")
        raise JWTError("bad payload") from e
    if not isinstance(raw, dict):  # pragma: no cover defensive
        _inc_jwt_rejected("bad_payload")
        raise JWTError("bad payload type")
    # Default issuer if absent
    raw.setdefault("iss", "yuplan")
    token_type = raw.get("type")
    if token_type not in ("access", "refresh"):
        _inc_jwt_rejected("type")
        raise JWTError("unknown token type")
    # Validate required claims and types
    def _req(key: str, t: type) -> Any:
        if key not in raw:
            _inc_jwt_rejected(key)
            raise JWTError(f"missing claim {key}")
        val = raw[key]
        if not isinstance(val, t):
            _inc_jwt_rejected(key)
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
        _inc_jwt_rejected("nbf")
        raise JWTError("nbf")
    aud_val = raw.get("aud")
    now = int(time.time())
    # Temporal validation
    if verify_exp:
        if now > exp + leeway:
            _inc_jwt_rejected("exp")
            raise JWTError("token expired")
        if nbf_val is not None and now + leeway < nbf_val:
            _inc_jwt_rejected("nbf")
            raise JWTError("token not yet valid")
        if iat > now + leeway:
            _inc_jwt_rejected("iat_future")
            raise JWTError("iat_future")
        if max_age is not None and (now - iat) > max_age + leeway:
            _inc_jwt_rejected("max_age")
            raise JWTError("max_age")
    # Issuer / audience
    if issuer and iss_val != issuer:
        _inc_jwt_rejected("iss")
        raise JWTError("iss")
    if audience:
        if aud_val is None:
            _inc_jwt_rejected("aud")
            raise JWTError("aud")
        if isinstance(aud_val, str):
            if aud_val != audience:
                _inc_jwt_rejected("aud")
                raise JWTError("aud")
        elif isinstance(aud_val, list):
            if audience not in aud_val:
                _inc_jwt_rejected("aud")
                raise JWTError("aud")
        else:
            _inc_jwt_rejected("aud")
            raise JWTError("aud")
    # Revocation hook
    if is_revoked and is_revoked(jti):
        _inc_jwt_rejected("revoked")
        raise JWTError("revoked")
    if token_type == "access":
        return AccessTokenPayload(sub=sub, role=role, tenant_id=tenant_id, jti=jti, iat=iat, exp=exp, iss=iss_val, type="access")
    return RefreshTokenPayload(sub=sub, role=role, tenant_id=tenant_id, jti=jti, iat=iat, exp=exp, iss=iss_val, type="refresh")


def issue_token_pair(*, user_id: int, role: str, tenant_id: int, secret: str, access_ttl: int = DEFAULT_ACCESS_TTL, refresh_ttl: int = DEFAULT_REFRESH_TTL, kid: str | None = None, audience: str = "api") -> tuple[str, str, str]:
    jti = generate_jti()
    now = int(time.time())
    access_payload: dict[str, Any] = {"sub": user_id, "role": role, "tenant_id": tenant_id, "jti": generate_jti(), "type": "access", "iss": "yuplan", "aud": audience, "iat": now, "exp": now + access_ttl}
    refresh_payload: dict[str, Any] = {"sub": user_id, "role": role, "tenant_id": tenant_id, "jti": jti, "type": "refresh", "iss": "yuplan", "aud": audience, "iat": now, "exp": now + refresh_ttl}
    # Derive kid from secret stable hash prefix for rotation signalling if not provided
    derived_kid = kid or hashlib.sha256(secret.encode()).hexdigest()[:8]
    access_token = encode(access_payload, secret=secret, ttl=access_ttl, kid=derived_kid)
    refresh_token = encode(refresh_payload, secret=secret, ttl=refresh_ttl, kid=derived_kid)
    return access_token, refresh_token, jti


def select_signing_secret(primary: str | None, candidates: list[str] | None) -> str:
    """Return primary secret if provided else first candidate; raise if none.

    Used to support rotation via JWT_SECRETS env (first used for signing while
    still accepting previous secrets for verification).
    """
    if primary:
        return primary
    if candidates:
        for c in candidates:
            if c:
                return c
    raise JWTError("no signing secret available")
