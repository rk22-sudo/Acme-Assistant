import os
import time

import jwt  # PyJWT

ISSUER = "handbook-assistant-mock"
TTL_SECONDS = 3600


class AuthError(Exception):
    """Token missing, invalid, expired, or tampered with."""


class AuthConfigurationError(RuntimeError):
    """JWT_SECRET is not set or too short."""


def _secret() -> str:
    secret = os.getenv("JWT_SECRET", "")
    if len(secret) < 32:
        raise AuthConfigurationError("JWT_SECRET must be set to at least 32 characters")
    return secret


def create_token(employee_id: str) -> str:
    now = int(time.time())
    claims = {"sub": employee_id, "iss": ISSUER, "iat": now, "exp": now + TTL_SECONDS}
    return jwt.encode(claims, _secret(), algorithm="HS256")


def verify_token(token: str) -> str:
    """Return the employee id (sub) from a valid token."""
    try:
        claims = jwt.decode(
            token,
            _secret(),
            algorithms=["HS256"],  # pinned: never trust the token's own 'alg' header
            issuer=ISSUER,
            options={"require": ["exp", "sub", "iss"]},
        )
    except jwt.PyJWTError as exc:
        raise AuthError(str(exc)) from exc
    return str(claims["sub"])