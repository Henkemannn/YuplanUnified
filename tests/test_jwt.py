import time

import pytest

from core.jwt_utils import JWTError, decode, issue_token_pair


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

@pytest.mark.parametrize("claim, mutate", [
    ("iss", lambda p: p.update({"iss": "other"})),
    ("aud-missing", lambda p: p.pop("aud", None)),
    ("nbf-future", lambda p: p.update({"nbf": int(time.time()) + 3600})),
    ("iat-future", lambda p: p.update({"iat": int(time.time()) + 4000})),
])
def test_jwt_claim_failures(claim, mutate, secrets):
    secret = secrets[0]
    import hashlib
    import hmac
    import json

    from core.jwt_utils import _b64url  # type: ignore
    now = int(time.time())
    payload = {"sub":1,"role":"admin","tenant_id":1,"jti":"x","type":"access","iss":"yuplan","iat":now,"exp":now+600,"aud":"api"}
    mutate(payload)
    header = {"alg":"HS256","typ":"JWT"}
    header_b = _b64url(json.dumps(header,separators=(",",":")).encode())
    body_b = _b64url(json.dumps(payload,separators=(",",":")).encode())
    sig = hmac.new(secret.encode(), f"{header_b}.{body_b}".encode(), hashlib.sha256).digest()
    token = f"{header_b}.{body_b}.{_b64url(sig)}"
    with pytest.raises(JWTError):
        decode(token, secret=secret, secrets_list=[], issuer="yuplan", audience="api", leeway=60, max_age=43200)
