"""Linking GitHub to a password account by redeeming the pending link token."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from tests.fakes import (
    NODE_PASSWORD,
    PRIMARY,
    USER_ID,
    FakeUnitOfWork,
    InMemoryGithubUsersRepo,
    encode_token,
    password_user,
)
from vce.auth import router as auth_router
from vce.auth import services
from vce.auth.exceptions import (
    GithubAlreadyLinked,
    InvalidCredentials,
    InvalidToken,
)
from vce.auth.schemas import (
    EmailLoginCredentials,
    GithubPendingLinkRequest,
)
from vce.auth.security import (
    create_access_token,
    create_github_pending_link_token,
    decode_token,
)
from vce.settings import (
    PASSWORD_MAX_LENGTH,
)
from vce.user.domain import User


def _link_pending(uow: FakeUnitOfWork, token: str, password: str = NODE_PASSWORD):
    return asyncio.run(services.link_github_with_password(token, password, uow))


def test_link_pending_links_github_and_logs_in(login_github):
    users = InMemoryGithubUsersRepo()
    user = password_user()
    users.users.append(user)
    uow = FakeUnitOfWork(users=users)

    tokens = _link_pending(uow, create_github_pending_link_token(USER_ID, 7))
    assert decode_token(tokens.access_token, expected_type="access")["userId"] == USER_ID
    assert user.github_id == 7
    # Linking and storing the refresh token are one transaction: a failure can't leave a link without a login
    assert len(uow.refresh_tokens.rows) == 1
    assert uow.commits == 1

    # The next GitHub login finds the account by its GitHub id, and password login still works
    tokens = login_github(users, PRIMARY)
    assert decode_token(tokens.access_token, expected_type="access")["userId"] == USER_ID
    assert users.users == [user]
    login = EmailLoginCredentials(email="octo@example.com", password=NODE_PASSWORD)
    assert asyncio.run(services.login_with_password(login, FakeUnitOfWork(users=users))).access_token


def test_link_pending_with_wrong_password_rejected():
    uow = FakeUnitOfWork()
    user = password_user()
    uow.users.users.append(user)
    with pytest.raises(InvalidCredentials):
        _link_pending(uow, create_github_pending_link_token(USER_ID, 7), password="wrong password")
    assert user.github_id is None
    assert uow.commits == 0


def test_link_pending_for_deleted_user_rejected():
    with pytest.raises(InvalidCredentials):
        _link_pending(FakeUnitOfWork(), create_github_pending_link_token(USER_ID, 7))


@pytest.mark.parametrize(
    "token",
    [
        lambda: encode_token(
            type="github_pending_link", githubId=7, exp=datetime.now(UTC) - timedelta(seconds=1)
        ),
        lambda: create_github_pending_link_token(USER_ID, 7)[:-2] + "xx",
        lambda: create_access_token(USER_ID),
    ],
    ids=["expired", "tampered", "access-token"],
)
def test_link_pending_with_invalid_token_rejected(token):
    uow = FakeUnitOfWork()
    user = password_user()
    uow.users.users.append(user)
    with pytest.raises(InvalidToken):
        _link_pending(uow, token())
    assert user.github_id is None


def test_link_pending_when_account_got_github_meanwhile_rejected():
    uow = FakeUnitOfWork()
    uow.users.users.append(password_user(github_id=99))
    with pytest.raises(GithubAlreadyLinked):
        _link_pending(uow, create_github_pending_link_token(USER_ID, 7))
    assert uow.users.users[0].github_id == 99


class ConcurrentlyLinkedUsersRepo(InMemoryGithubUsersRepo):
    """While the request waits for the row lock, a concurrent request links another GitHub account to the
    user and commits; the locked re-read sees that link."""

    async def lock(self, user: User):
        user.github_id = 99


def test_link_pending_when_account_linked_while_waiting_for_lock_rejected():
    users = ConcurrentlyLinkedUsersRepo()
    users.users.append(password_user())
    uow = FakeUnitOfWork(users=users)
    with pytest.raises(GithubAlreadyLinked):
        _link_pending(uow, create_github_pending_link_token(USER_ID, 7))
    assert users.users[0].github_id == 99
    assert uow.commits == 0


def test_link_pending_when_github_id_now_on_another_account_rejected():
    uow = FakeUnitOfWork()
    user = password_user()
    uow.users.users.append(user)
    uow.users.users.append(User(id=uuid.uuid7(), email=None, password=None, salt=None, github_id=7))
    with pytest.raises(GithubAlreadyLinked):
        _link_pending(uow, create_github_pending_link_token(USER_ID, 7))
    assert user.github_id is None


def test_link_pending_when_github_id_taken_before_commit_rejected():
    # The same GitHub id was linked to or registered as another account between the check and the commit
    uow = FakeUnitOfWork(failing_commits=1)
    uow.users.users.append(password_user())
    with pytest.raises(GithubAlreadyLinked):
        _link_pending(uow, create_github_pending_link_token(USER_ID, 7))
    assert uow.commits == 0


@pytest.mark.parametrize(
    "raised, status",
    [(InvalidToken("expired"), 401), (InvalidCredentials(), 401), (GithubAlreadyLinked(), 409)],
)
def test_link_pending_router_errors(monkeypatch, raised, status):
    async def link_github_with_password(*args):
        raise raised

    monkeypatch.setattr(auth_router.services, "link_github_with_password", link_github_with_password)
    body = GithubPendingLinkRequest(pending_link_token="token", password="password")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth_router.link_github_pending(body, FakeUnitOfWork()))
    assert exc.value.status_code == status


def test_link_pending_request_password_length_limit():
    with pytest.raises(ValidationError):
        GithubPendingLinkRequest(pending_link_token="token", password="x" * (PASSWORD_MAX_LENGTH + 1))
