import time
import hashlib
import hmac
import json

import pytest

from core.jwt_utils import JWTError, _b64url, decode, encode, issue_token_pair


def _make_hs(secret="s1"):
    return secret


@pytest.fixture()
def secrets():
    return ["alpha_secret", "beta_secret"]


@pytest.fixture()
def primary(secrets):
    return secrets[0]


@pytest.fixture()
def cfg(app):  # type: ignore
    c = app.config
    c["JWT_ISSUER"] = "yuplan"
    c["JWT_AUDIENCE"] = "api"
    c["JWT_MAX_AGE_SECONDS"] = 43200
    c["JWT_LEEWAY_SECONDS"] = 60
    return c


def test_jwt_rotation_accepts_old_and_new(secrets):
    # sign with first then second; both should validate while both in list
    a = secrets[0]
    b = secrets[1]
    at1, _, _ = issue_token_pair(user_id=1, role="admin", tenant_id=1, secret=a)
    at2, _, _ = issue_token_pair(user_id=1, role="admin", tenant_id=1, secret=b)
    # decode each with combined list
    assert decode(at1, secret=a, secrets_list=[b]).get("sub") == 1
    assert decode(at2, secret=b, secrets_list=[a]).get("sub") == 1


@pytest.mark.parametrize(
    "claim, mutate",
    [
        ("iss", lambda p: p.update({"iss": "other"})),
        ("aud-missing", lambda p: p.pop("aud", None)),
        ("nbf-future", lambda p: p.update({"nbf": int(time.time()) + 3600})),
        ("iat-future", lambda p: p.update({"iat": int(time.time()) + 4000})),
    ],
)
def test_jwt_claim_failures(claim, mutate, secrets):
    secret = secrets[0]
    import hashlib
    import hmac
    import json

    from core.jwt_utils import _b64url  # type: ignore

    now = int(time.time())
    payload = {
        "sub": 1,
        "role": "admin",
        "tenant_id": 1,
        "auth_version": 1,
        "jti": "x",
        "type": "access",
        "iss": "yuplan",
        "iat": now,
        "exp": now + 600,
        "aud": "api",
    }
    mutate(payload)
    header = {"alg": "HS256", "typ": "JWT"}
    header_b = _b64url(json.dumps(header, separators=(",", ":")).encode())
    body_b = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(secret.encode(), f"{header_b}.{body_b}".encode(), hashlib.sha256).digest()
    token = f"{header_b}.{body_b}.{_b64url(sig)}"
    with pytest.raises(JWTError):
        decode(
            token,
            secret=secret,
            secrets_list=[],
            issuer="yuplan",
            audience="api",
            leeway=60,
            max_age=43200,
        )


def _hmac_token_with_algorithm(algorithm: str, secret: str, kid: str | None = "0") -> str:
    now = int(time.time())
    header = {"alg": algorithm, "typ": "JWT"}
    if kid is not None:
        header["kid"] = kid
    payload = {
        "sub": 1,
        "role": "admin",
        "tenant_id": 1,
        "auth_version": 1,
        "jti": "synthetic-algorithm-jti",
        "type": "access",
        "iss": "yuplan",
        "aud": "api",
        "iat": now,
        "exp": now + 600,
    }
    header_b = _b64url(json.dumps(header, separators=(",", ":")).encode())
    payload_b = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    message = f"{header_b}.{payload_b}".encode()
    signature = _b64url(hmac.new(secret.encode(), message, hashlib.sha256).digest())
    return f"{header_b}.{payload_b}.{signature}"


def test_hs256_accepts_and_rs256_hmac_is_rejected():
    secret = "synthetic-hs256-primary"
    payload = {
        "sub": 1,
        "role": "admin",
        "tenant_id": 1,
        "auth_version": 1,
        "jti": "synthetic-hs256-jti",
        "type": "access",
    }
    hs256 = encode(payload, secret=secret, ttl=600)
    assert decode(hs256, secret=secret)["type"] == "access"

    with pytest.raises(JWTError):
        decode(_hmac_token_with_algorithm("RS256", secret, kid="0"), secrets_list=[secret])
    with pytest.raises(JWTError):
        decode(
            _hmac_token_with_algorithm(
                "RS256",
                secret,
                kid=hashlib.sha256(secret.encode()).hexdigest()[:8],
            ),
            secrets_list=[secret],
        )
    with pytest.raises(JWTError):
        decode(_hmac_token_with_algorithm("RS256", secret, kid=None), secrets_list=[secret])


@pytest.mark.parametrize("algorithm", ("none", "HS384", "HS512", "ES256", "synthetic"))
def test_non_hs256_algorithms_are_rejected(algorithm):
    with pytest.raises(JWTError):
        decode(
            _hmac_token_with_algorithm(algorithm, "synthetic-algorithm-secret"),
            secrets_list=["synthetic-algorithm-secret"],
        )


def test_hs256_rotation_rejects_removed_key_and_keeps_primary_signing():
    old_secret = "synthetic-hs256-old"
    new_secret = "synthetic-hs256-new"
    old_token = encode(
        {
            "sub": 1,
            "role": "admin",
            "tenant_id": 1,
            "auth_version": 1,
            "jti": "synthetic-old-jti",
            "type": "access",
        },
        secret=old_secret,
        ttl=600,
    )
    with pytest.raises(JWTError):
        decode(old_token, secret=new_secret, secrets_list=[new_secret])
    assert decode(old_token, secret=new_secret, secrets_list=[new_secret, old_secret])["sub"] == 1
    current_token = encode(
        {
            "sub": 1,
            "role": "admin",
            "tenant_id": 1,
            "auth_version": 1,
            "jti": "synthetic-current-jti",
            "type": "access",
        },
        secret=new_secret,
        ttl=600,
    )
    assert decode(current_token, secret=new_secret, secrets_list=[old_secret])["sub"] == 1
