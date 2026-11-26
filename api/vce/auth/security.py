import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from vce.auth.domain import RefreshToken, TokenType
from vce.auth.exceptions import InvalidToken
from vce.settings import (
    JWT_ACCESS_TOKEN_EXPIRY_SECONDS,
    JWT_ALGORITHM,
    JWT_AUDIENCE,
    JWT_GITHUB_PENDING_LINK_TOKEN_EXPIRY_SECONDS,
    JWT_REFRESH_TOKEN_EXPIRY_SECONDS,
    JWT_SECRET_KEY,
)

if not JWT_SECRET_KEY:
    raise RuntimeError("Missing JWT_SECRET_KEY env variable")


# Claims each token type carries besides type/aud/iat/exp, by how they are validated
UUID_CLAIMS: dict[TokenType, list[str]] = {
    "access": ["userId"],
    "refresh": ["userId", "jti", "fam"],
    "github_pending_link": ["userId"],
}
INT_CLAIMS: dict[TokenType, list[str]] = {
    "access": [],
    "refresh": [],
    "github_pending_link": ["githubId"],
}


def encode_jwt(claims: dict[str, Any], expiry_seconds: int, now: datetime) -> str:
    payload = {
        **claims,
        "aud": JWT_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(seconds=expiry_seconds),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str, required: list[str]) -> dict[str, Any]:
    return jwt.decode(
        token,
        JWT_SECRET_KEY,
        algorithms=[JWT_ALGORITHM],
        audience=JWT_AUDIENCE,
        options={"require": required},
    )


def create_access_token(user_id: uuid.UUID) -> str:
    return encode_jwt(
        {"userId": str(user_id), "type": "access"}, JWT_ACCESS_TOKEN_EXPIRY_SECONDS, datetime.now(UTC)
    )


def create_refresh_token(user_id: uuid.UUID, family_id: uuid.UUID | None = None) -> RefreshToken:
    """
    Without family_id a new family is started: each logged-in session has its own family_id
    which carries over on rotation until revoked (e.g. on logout or detected reuse).
    """
    family_id = family_id or uuid.uuid7()
    now = datetime.now(UTC)
    jti = uuid.uuid7()
    claims = {"userId": str(user_id), "type": "refresh", "jti": str(jti), "fam": str(family_id)}
    token = encode_jwt(claims, JWT_REFRESH_TOKEN_EXPIRY_SECONDS, now)
    return RefreshToken(
        jti=jti,
        user_id=user_id,
        family_id=family_id,
        created_at=now,
        expires_at=now + timedelta(seconds=JWT_REFRESH_TOKEN_EXPIRY_SECONDS),
        token=token,
    )


def create_github_pending_link_token(user_id: uuid.UUID, github_id: int) -> str:
    """
    Issued when a GitHub login finds the GitHub email on an existing password account (user_id). It records
    that the backend authenticated the GitHub account github_id, so the user only has to confirm the
    account's password to link the two. Signed, so neither id can be swapped by the client.
    """
    claims = {"userId": str(user_id), "type": "github_pending_link", "githubId": github_id}
    return encode_jwt(claims, JWT_GITHUB_PENDING_LINK_TOKEN_EXPIRY_SECONDS, datetime.now(UTC))


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    uuid_claims = UUID_CLAIMS[expected_type]
    int_claims = INT_CLAIMS[expected_type]
    required = ["type", "aud", "iat", "exp", *uuid_claims, *int_claims]
    try:
        payload = decode_jwt(token, required)
    except jwt.PyJWTError as e:
        raise InvalidToken(str(e)) from e
    if payload["type"] != expected_type:
        raise InvalidToken(f"Expected {expected_type} token, got {payload['type']}")

    for claim in uuid_claims:
        try:
            payload[claim] = uuid.UUID(payload[claim])
        except (TypeError, ValueError, AttributeError) as e:
            raise InvalidToken(f"Invalid {claim} claim") from e
    for claim in int_claims:
        if type(payload[claim]) is not int:
            raise InvalidToken(f"Invalid {claim} claim")
    return payload
