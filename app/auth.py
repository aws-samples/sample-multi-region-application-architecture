"""
JWT authentication middleware for Flask — validates Cognito access tokens.

Uses the Cognito JWKS endpoint to verify RS256 signatures. Public keys are
cached in-memory with a 1-hour TTL to avoid fetching on every request.
"""

import os
import time
import json
import logging
from functools import wraps

import requests
from flask import request, jsonify

# 'jose' comes from the python-jose[cryptography] package — it handles
# JWT decoding and RS256 signature verification using public keys.
from jose import jwt, JWTError

logger = logging.getLogger(__name__)

# Configuration from environment variables (set by CloudFormation / ECS task def)
COGNITO_REGION = os.environ.get("COGNITO_REGION", "us-east-1")
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "")

# Derived values
COGNITO_ISSUER = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"
JWKS_URL = f"{COGNITO_ISSUER}/.well-known/jwks.json"

# Module-level cache for JWKS keys (survives across Flask requests)
_jwks_cache = None
_jwks_fetched_at = 0
JWKS_TTL_SECONDS = 3600  # 1 hour


def _fetch_jwks():
    """Fetch JSON Web Key Set from Cognito and cache it.

    The JWKS contains the public keys used to verify JWT signatures.
    We cache it to avoid an HTTP call on every request.
    """
    global _jwks_cache, _jwks_fetched_at
    try:
        response = requests.get(JWKS_URL, timeout=5)
        response.raise_for_status()
        _jwks_cache = response.json()
        _jwks_fetched_at = time.time()
        logger.info("Fetched JWKS from %s (%d keys)", JWKS_URL, len(_jwks_cache.get("keys", [])))
    except Exception as e:
        logger.error("Failed to fetch JWKS from %s: %s", JWKS_URL, e)
        if _jwks_cache is None:
            raise


def _get_jwks(force_refresh=False):
    """Return cached JWKS, refreshing if expired or forced.

    Args:
        force_refresh: If True, fetch fresh keys regardless of TTL.
                       Used when a token's 'kid' isn't found in the cache
                       (handles Cognito key rotation).
    """
    if force_refresh or _jwks_cache is None or (time.time() - _jwks_fetched_at) > JWKS_TTL_SECONDS:
        _fetch_jwks()
    return _jwks_cache


def validate_token(token: str) -> dict:
    """Validate a Cognito JWT access token and return its claims.

    Steps:
    1. Decode the JWT header to get the key ID (kid)
    2. Find the matching public key in the JWKS
    3. Verify the signature, expiry, and issuer

    Args:
        token: The raw JWT string (without 'Bearer ' prefix)

    Returns:
        dict of decoded JWT claims (sub, email, token_use, etc.)

    Raises:
        ValueError: If the token is invalid for any reason
    """
    # Step 1: Read the unverified header to get the key ID
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError:
        raise ValueError("Invalid token format")

    kid = unverified_header.get("kid")
    if not kid:
        raise ValueError("Token missing key ID")

    # Step 2: Find the matching public key in JWKS
    jwks = _get_jwks()
    key = next((k for k in jwks.get("keys", []) if k["kid"] == kid), None)

    # If key not found, try refreshing JWKS once (handles key rotation)
    if key is None:
        jwks = _get_jwks(force_refresh=True)
        key = next((k for k in jwks.get("keys", []) if k["kid"] == kid), None)

    if key is None:
        raise ValueError("Token signing key not found")

    # Step 3: Verify signature, expiry, and issuer
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=COGNITO_ISSUER,
            options={"verify_aud": False},  # Cognito access tokens don't have 'aud'
        )
    except jwt.ExpiredSignatureError:
        raise ValueError("Token expired")
    except JWTError:
        raise ValueError("Invalid token")

    # Verify this is an access token (not an ID token)
    if claims.get("token_use") != "access":
        raise ValueError("Invalid token type")

    return claims


def require_auth(f):
    """Flask decorator that enforces JWT authentication on a route.

    Usage:
        @app.route('/api/airports')
        @require_auth
        def read_airports():
            # request.user_claims contains the decoded JWT claims
            ...

    If the token is missing or invalid, returns 401 with an error message.
    If valid, attaches decoded claims to request.user_claims.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Fail closed — reject all requests if auth is not configured
        if not COGNITO_USER_POOL_ID:
            logger.error("COGNITO_USER_POOL_ID is not configured — rejecting request")
            return jsonify({"error": "Authentication not configured"}), 503

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization header required"}), 401

        token = auth_header[7:]  # Strip "Bearer " prefix

        try:
            claims = validate_token(token)
            # Attach claims to the request so route handlers can access user info
            request.user_claims = claims
        except ValueError as e:
            return jsonify({"error": str(e)}), 401

        return f(*args, **kwargs)

    return decorated
