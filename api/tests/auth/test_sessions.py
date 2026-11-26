"""Refresh token rotation, logout and the user behind an access token."""

import asyncio
import uuid

import pytest

from tests.fakes import (
    USER_ID,
    FakeUnitOfWork,
    password_user,
)
from vce.auth import services
from vce.auth.exceptions import (
    InvalidToken,
    RefreshTokenReused,
)
from vce.auth.security import (
    create_access_token,
    decode_token,
)
from vce.user.domain import User


class FakeUsersRepo:
    async def get_by_id(self, id: uuid.UUID) -> User | None:
        return User(id=id, email="a@b.c", password=None, salt=None, github_id=None)


@pytest.fixture
def ctx():
    return FakeUnitOfWork(users=FakeUsersRepo())


def _start(ctx, user_id=USER_ID):
    return asyncio.run(services._start_session(user_id, ctx))


def _rotate(ctx, refresh_token):
    return asyncio.run(services.rotate_refresh_token(refresh_token, ctx))


def test_rotation_replaces_token_in_same_family(ctx):
    token_repo = ctx.refresh_tokens
    first = _start(ctx)
    old = decode_token(first.refresh_token, "refresh")

    second = _rotate(ctx, first.refresh_token)
    new = decode_token(second.refresh_token, "refresh")

    assert new["jti"] != old["jti"]
    assert new["fam"] == old["fam"]
    assert set(token_repo.rows) == {new["jti"]}
    assert decode_token(second.access_token, "access")["userId"] == USER_ID
    # Consuming the old token and storing the new one is one transaction
    assert ctx.commits == 1


def test_reuse_revokes_whole_family(ctx):
    token_repo = ctx.refresh_tokens
    first = _start(ctx)
    second = _rotate(ctx, first.refresh_token)

    with pytest.raises(RefreshTokenReused):
        _rotate(ctx, first.refresh_token)

    assert token_repo.rows == {}
    # The revocation is committed although the request fails
    assert ctx.commits == 2
    # The legitimately rotated token is dead too
    with pytest.raises(RefreshTokenReused):
        _rotate(ctx, second.refresh_token)


def test_reuse_does_not_affect_other_sessions(ctx):
    token_repo = ctx.refresh_tokens
    session_a = _start(ctx)
    session_b = _start(ctx)
    _rotate(ctx, session_a.refresh_token)

    with pytest.raises(RefreshTokenReused):
        _rotate(ctx, session_a.refresh_token)

    assert token_repo.families() == {decode_token(session_b.refresh_token, "refresh")["fam"]}
    _rotate(ctx, session_b.refresh_token)


def test_logout_revokes_family_only(ctx):
    session_a = _start(ctx)
    session_b = _start(ctx)

    asyncio.run(services.logout(session_a.refresh_token, ctx))
    assert ctx.commits == 1

    with pytest.raises(RefreshTokenReused):
        _rotate(ctx, session_a.refresh_token)
    _rotate(ctx, session_b.refresh_token)


def test_logout_with_invalid_token_is_noop(ctx):
    token_repo = ctx.refresh_tokens
    _start(ctx)
    asyncio.run(services.logout("garbage", ctx))
    assert len(token_repo.rows) == 1


def test_access_token_cannot_be_used_to_refresh(ctx):
    pair = _start(ctx)
    with pytest.raises(InvalidToken):
        _rotate(ctx, pair.access_token)


def test_user_from_access_token():
    uow = FakeUnitOfWork()
    user = password_user()
    uow.users.users.append(user)
    assert asyncio.run(services.get_user_from_access_token(create_access_token(USER_ID), uow)) is user
    assert uow.commits == 0


def test_user_from_access_token_of_deleted_user_rejected():
    with pytest.raises(InvalidToken):
        asyncio.run(services.get_user_from_access_token(create_access_token(USER_ID), FakeUnitOfWork()))
