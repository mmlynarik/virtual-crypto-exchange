import hashlib
import hmac
import secrets
import unicodedata
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
    JWT_REFRESH_TOKEN_EXPIRY_SECONDS,
    JWT_SECRET_KEY,
)

# Fail fast: the app imports this module at startup (via the auth router)
if not JWT_SECRET_KEY:
    raise RuntimeError("Missing JWT_SECRET_KEY env variable")

# Scrypt parameters match Node's crypto.scrypt defaults used by the web app, so existing hashes verify.
SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_KEY_LENGTH = 64


def generate_salt() -> str:
    return secrets.token_hex(16)


def hash_password(password: str, salt: str) -> str:
    return hashlib.scrypt(
        unicodedata.normalize("NFC", password).encode(),
        salt=salt.encode(),
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_KEY_LENGTH,
    ).hex()


def verify_password(password: str, hashed_password: str, salt: str) -> bool:
    return hmac.compare_digest(hash_password(password, salt), hashed_password)


def _encode(claims: dict[str, Any], expiry_seconds: int, now: datetime) -> str:
    payload = {
        **claims,
        "aud": JWT_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(seconds=expiry_seconds),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_access_token(user_id: int) -> str:
    now = datetime.now(UTC)
    return _encode({"userId": user_id, "type": "access"}, JWT_ACCESS_TOKEN_EXPIRY_SECONDS, now)


def create_refresh_token(user_id: int, family_id: str) -> tuple[str, RefreshToken]:
    now = datetime.now(UTC)
    jti = str(uuid.uuid7())
    token = _encode(
        {"userId": user_id, "type": "refresh", "jti": jti, "fam": family_id},
        JWT_REFRESH_TOKEN_EXPIRY_SECONDS,
        now,
    )
    record = RefreshToken(
        jti=jti,
        user_id=user_id,
        family_id=family_id,
        created_at=now,
        expires_at=now + timedelta(seconds=JWT_REFRESH_TOKEN_EXPIRY_SECONDS),
    )
    return token, record


def new_family_id() -> str:
    return str(uuid.uuid7())


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    required = ["userId", "type", "aud", "iat", "exp"]
    if expected_type == "refresh":
        required += ["jti", "fam"]
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            audience=JWT_AUDIENCE,
            options={"require": required},
        )
    except jwt.PyJWTError as e:
        raise InvalidToken(str(e)) from e
    if payload["type"] != expected_type:
        raise InvalidToken(f"Expected {expected_type} token, got {payload['type']}")
    if not isinstance(payload["userId"], int):
        raise InvalidToken("Invalid userId claim")
    return payload
