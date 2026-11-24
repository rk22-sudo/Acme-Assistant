import os
import time

import jwt  # PyJWT

ISSUER = "handbook-assistant-mock"
TTL_SECONDS = 3600
ACTION_ISSUER = "handbook-assistant-action"
ACTION_TTL_SECONDS = 300


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


def create_action_token(employee_id: str, name: str, args: dict) -> str:
    now = int(time.time())
    claims = {
        "sub": employee_id,
        "tool": name,
        "args": args,
        "iss": ACTION_ISSUER,
        "exp": now + ACTION_TTL_SECONDS,
    }
    return jwt.encode(claims, _secret(), algorithm="HS256")


def verify_action_token(token: str) -> tuple[str, str, dict]:
    """Validate a short-lived confirmation token and return its bound action."""
    try:
        claims = jwt.decode(
            token,
            _secret(),
            algorithms=["HS256"],
            issuer=ACTION_ISSUER,
            options={"require": ["exp", "sub", "tool", "args", "iss"]},
        )
    except jwt.PyJWTError as exc:
        raise AuthError(str(exc)) from exc
    if not isinstance(claims["args"], dict):
        raise AuthError("Action args must be an object")
    return str(claims["sub"]), str(claims["tool"]), claims["args"]
