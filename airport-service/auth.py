"""
JWT authentication for Airport Lambda — validates Cognito access tokens from ALB.
Same auth module as flights-service.
"""

import os
import time
import json
import logging
from urllib.request import urlopen, Request

from jose import jwt, JWTError

logger = logging.getLogger(__name__)

COGNITO_REGION = os.environ.get("COGNITO_REGION", "us-east-1")
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "")

COGNITO_ISSUER = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"
JWKS_URL = f"{COGNITO_ISSUER}/.well-known/jwks.json"

_jwks_cache = None
_jwks_fetched_at = 0
JWKS_TTL_SECONDS = 3600


def _fetch_jwks():
    global _jwks_cache, _jwks_fetched_at
    try:
        req = Request(JWKS_URL)
        with urlopen(req, timeout=5) as resp:
            _jwks_cache = json.loads(resp.read())
        _jwks_fetched_at = time.time()
    except Exception as e:
        logger.error("Failed to fetch JWKS: %s", e)
        if _jwks_cache is None:
            raise


def _get_jwks(force_refresh=False):
    if force_refresh or _jwks_cache is None or (time.time() - _jwks_fetched_at) > JWKS_TTL_SECONDS:
        _fetch_jwks()
    return _jwks_cache


def validate_token(token: str) -> dict:
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError:
        raise ValueError("Invalid token format")

    kid = unverified_header.get("kid")
    if not kid:
        raise ValueError("Token missing key ID")

    jwks = _get_jwks()
    key = next((k for k in jwks.get("keys", []) if k["kid"] == kid), None)
    if key is None:
        jwks = _get_jwks(force_refresh=True)
        key = next((k for k in jwks.get("keys", []) if k["kid"] == kid), None)
    if key is None:
        raise ValueError("Token signing key not found")

    try:
        claims = jwt.decode(token, key, algorithms=["RS256"], issuer=COGNITO_ISSUER, options={"verify_aud": False})
    except jwt.ExpiredSignatureError:
        raise ValueError("Token expired")
    except JWTError:
        raise ValueError("Invalid token")

    if claims.get("token_use") != "access":
        raise ValueError("Invalid token type")
    return claims


def validate_request(event: dict) -> dict:
    # Fail closed — reject all requests if auth is not configured
    if not COGNITO_USER_POOL_ID:
        raise ValueError("Authentication not configured — COGNITO_USER_POOL_ID is empty")
    headers = event.get("headers") or {}
    auth_header = headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise ValueError("Authorization header required")
    return validate_token(auth_header[7:])
