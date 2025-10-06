import time

import pytest

from core.jwt_utils import (
    DEFAULT_ACCESS_TTL,
    SKEW_SECS,
    JWTError,
    decode,
    encode,
    issue_token_pair,
)

SECRET = "test-secret"


def mutate_token_signature(token: str) -> str:
    head, payload, sig = token.split(".")
    # Flip last char deterministically
    new_last = "A" if not sig.endswith("A") else "B"
    sig = sig[:-1] + new_last
    return f"{head}.{payload}.{sig}"


def test_issue_and_decode_access_and_refresh():
    access, refresh, refresh_jti = issue_token_pair(user_id=1, role="admin", tenant_id=7, secret=SECRET)
    a_payload = decode(access, secret=SECRET)
    r_payload = decode(refresh, secret=SECRET)
    assert a_payload["type"] == "access"
    assert r_payload["type"] == "refresh"
    assert a_payload["sub"] == 1
    assert r_payload["sub"] == 1
    assert r_payload["jti"] == refresh_jti
    assert a_payload["jti"] != r_payload["jti"], "access token must have distinct jti"


def test_decode_missing_claim():
    token = encode({"role": "user", "tenant_id": 1, "jti": "abc", "type": "access"}, secret=SECRET, ttl=60)
    with pytest.raises(JWTError) as exc:
        decode(token, secret=SECRET)
    assert "missing claim sub" in str(exc.value)


def test_decode_unknown_type():
    token = encode({"role": "user", "tenant_id": 1, "jti": "abc", "sub": 5, "type": "other"}, secret=SECRET, ttl=60)
    with pytest.raises(JWTError) as exc:
        decode(token, secret=SECRET)
    assert "unknown token type" in str(exc.value)


def test_decode_bad_signature():
    token = encode({"sub": 2, "role": "user", "tenant_id": 1, "jti": "abc", "type": "access"}, secret=SECRET, ttl=60)
    tampered = mutate_token_signature(token)
    with pytest.raises(JWTError) as exc:
        decode(tampered, secret=SECRET)
    assert "bad signature" in str(exc.value)


def test_decode_expired_token():
    now = int(time.time())
    expired_exp = now - (SKEW_SECS + 5)
    token = encode({"sub": 3, "role": "user", "tenant_id": 1, "jti": "abc", "type": "access", "exp": expired_exp}, secret=SECRET, ttl=DEFAULT_ACCESS_TTL)
    with pytest.raises(JWTError) as exc:
        decode(token, secret=SECRET)
    assert "token expired" in str(exc.value)


def test_decode_expired_within_skew_ok():
    now = int(time.time())
    exp_within_skew = now - (SKEW_SECS - 5)
    token = encode({"sub": 4, "role": "user", "tenant_id": 1, "jti": "abc", "type": "access", "exp": exp_within_skew}, secret=SECRET, ttl=DEFAULT_ACCESS_TTL)
    payload = decode(token, secret=SECRET)
    assert payload["sub"] == 4


def test_decode_not_yet_valid_nbf():
    now = int(time.time())
    future_nbf = now + SKEW_SECS + 5
    token = encode({"sub": 5, "role": "user", "tenant_id": 1, "jti": "abc", "type": "access", "nbf": future_nbf}, secret=SECRET, ttl=60)
    with pytest.raises(JWTError) as exc:
        decode(token, secret=SECRET)
    assert "token not yet valid" in str(exc.value)


def test_default_issuer_injected():
    token = encode({"sub": 9, "role": "user", "tenant_id": 2, "jti": "abc", "type": "access"}, secret=SECRET, ttl=60)
    payload = decode(token, secret=SECRET)
    assert payload["iss"] == "yuplan"
