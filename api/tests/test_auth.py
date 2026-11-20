import asyncio
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from vce.auth import services
from vce.auth.domain import RefreshToken
from vce.auth.exceptions import InvalidToken, RefreshTokenReused
from vce.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from vce.settings import JWT_ALGORITHM, JWT_AUDIENCE, JWT_SECRET_KEY
from vce.user.domain import User

# Generated with Node (same call as web/src/lib/auth/passwordHasher.ts):
# crypto.scrypt("pässword 123".normalize(), "a1b2c3d4e5f60718293a4b5c6d7e8f90", 64)
NODE_SALT = "a1b2c3d4e5f60718293a4b5c6d7e8f90"
NODE_HASH = (
    "438f15f9f77ccfb490cd07a576d1c0992a6ce3d93a0f8507973d2347b27f3693"
    "0ee8d8290bddc7fee9a3618278a75fbb8672f6c77578412e4cb6f799e8e5f846"
)


# --- password hashing ---


def test_hash_password_matches_node_scrypt():
    assert hash_password("pässword 123", NODE_SALT) == NODE_HASH


def test_verify_password():
    assert verify_password("pässword 123", NODE_HASH, NODE_SALT)
    assert not verify_password("wrong password", NODE_HASH, NODE_SALT)


# --- tokens ---


def test_access_token_roundtrip():
    payload = decode_token(create_access_token(42), expected_type="access")
    assert payload["userId"] == 42
    assert payload["aud"] == JWT_AUDIENCE


def test_refresh_token_roundtrip():
    token, record = create_refresh_token(42, "family-1")
    payload = decode_token(token, expected_type="refresh")
    assert payload["jti"] == record.jti
    assert payload["fam"] == "family-1"
    assert record.user_id == 42


def test_token_type_is_enforced():
    refresh, _ = create_refresh_token(42, "family-1")
    with pytest.raises(InvalidToken):
        decode_token(refresh, expected_type="access")
    with pytest.raises(InvalidToken):
        decode_token(create_access_token(42), expected_type="refresh")


def _encode(**overrides):
    now = datetime.now(UTC)
    claims = {
        "userId": 42,
        "type": "access",
        "aud": JWT_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode(claims, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def test_wrong_audience_rejected():
    with pytest.raises(InvalidToken):
        decode_token(_encode(aud="other"), expected_type="access")


def test_expired_token_rejected():
    with pytest.raises(InvalidToken):
        decode_token(_encode(exp=datetime.now(UTC) - timedelta(seconds=1)), expected_type="access")


def test_bad_signature_rejected():
    token = jwt.encode(
        {"userId": 42, "type": "access", "aud": JWT_AUDIENCE}, "other-secret", algorithm="HS256"
    )
    with pytest.raises(InvalidToken):
        decode_token(token, expected_type="access")


# --- rotation & revocation (services with in-memory fakes) ---


class FakeTokenRepo:
    def __init__(self):
        self.rows: dict[str, RefreshToken] = {}

    async def add(self, token: RefreshToken):
        self.rows[token.jti] = token

    async def consume(self, jti: str) -> RefreshToken | None:
        return self.rows.pop(jti, None)

    async def revoke_family(self, family_id: str):
        self.rows = {k: v for k, v in self.rows.items() if v.family_id != family_id}

    async def delete_expired_for_user(self, user_id: int):
        now = datetime.now(UTC)
        self.rows = {k: v for k, v in self.rows.items() if not (v.user_id == user_id and v.expires_at < now)}

    def families(self) -> set[str]:
        return {r.family_id for r in self.rows.values()}


class FakeUsersRepo:
    async def get_by_id(self, id: int) -> User | None:
        return User(id=id, email="a@b.c", password=None, salt=None, github_id=None, github_name=None)


class FakeSession:
    async def commit(self):
        pass


@pytest.fixture
def ctx():
    return FakeUsersRepo(), FakeTokenRepo(), FakeSession()


def _start(ctx, user_id=1):
    _, token_repo, session = ctx
    return asyncio.run(services.start_session(user_id, token_repo, session))


def _rotate(ctx, refresh_token):
    users, token_repo, session = ctx
    return asyncio.run(services.rotate_refresh_token(refresh_token, users, token_repo, session))


def test_rotation_replaces_token_in_same_family(ctx):
    _, token_repo, _ = ctx
    first = _start(ctx)
    old = decode_token(first.refresh_token, "refresh")

    second = _rotate(ctx, first.refresh_token)
    new = decode_token(second.refresh_token, "refresh")

    assert new["jti"] != old["jti"]
    assert new["fam"] == old["fam"]
    assert set(token_repo.rows) == {new["jti"]}
    assert decode_token(second.access_token, "access")["userId"] == 1


def test_reuse_revokes_whole_family(ctx):
    _, token_repo, _ = ctx
    first = _start(ctx)
    second = _rotate(ctx, first.refresh_token)

    with pytest.raises(RefreshTokenReused):
        _rotate(ctx, first.refresh_token)

    assert token_repo.rows == {}
    # The legitimately rotated token is dead too
    with pytest.raises(RefreshTokenReused):
        _rotate(ctx, second.refresh_token)


def test_reuse_does_not_affect_other_sessions(ctx):
    _, token_repo, _ = ctx
    session_a = _start(ctx)
    session_b = _start(ctx)
    _rotate(ctx, session_a.refresh_token)

    with pytest.raises(RefreshTokenReused):
        _rotate(ctx, session_a.refresh_token)

    assert token_repo.families() == {decode_token(session_b.refresh_token, "refresh")["fam"]}
    _rotate(ctx, session_b.refresh_token)


def test_logout_revokes_family_only(ctx):
    _, token_repo, session = ctx
    session_a = _start(ctx)
    session_b = _start(ctx)

    asyncio.run(services.logout(session_a.refresh_token, token_repo, session))

    with pytest.raises(RefreshTokenReused):
        _rotate(ctx, session_a.refresh_token)
    _rotate(ctx, session_b.refresh_token)


def test_logout_with_invalid_token_is_noop(ctx):
    _, token_repo, session = ctx
    _start(ctx)
    asyncio.run(services.logout("garbage", token_repo, session))
    assert len(token_repo.rows) == 1


def test_access_token_cannot_be_used_to_refresh(ctx):
    pair = _start(ctx)
    with pytest.raises(InvalidToken):
        _rotate(ctx, pair.access_token)
