"""Logging in with GitHub: the GitHub user, login_with_github and its router errors."""

import asyncio
from typing import Any

import pytest
from fastapi import HTTPException

from tests.fakes import (
    PRIMARY,
    USER_ID,
    FakeUnitOfWork,
    InMemoryGithubUsersRepo,
    github_client,
)
from vce.auth import router as auth_router
from vce.auth.exceptions import (
    GithubAuthError,
    GithubEmailTaken,
    GithubLinkRequired,
)
from vce.auth.github import get_github_user
from vce.auth.schemas import (
    GithubCode,
)
from vce.auth.security import (
    decode_token,
)
from vce.user.domain import User
from vce.user.exceptions import UserAlreadyExists


def test_github_user_uses_primary_verified_email():
    client = github_client(
        [
            {"email": "other@example.com", "primary": False, "verified": True},
            {"email": "Octo.Cat@Example.com", "primary": True, "verified": True},
        ]
    )
    user = asyncio.run(get_github_user(client, "gh-token"))
    assert (user.id, user.email) == (7, "octo.cat@example.com")


@pytest.mark.parametrize(
    "emails",
    [
        [],
        [{"email": "a@example.com", "primary": True, "verified": False}],
        [{"email": "a@example.com", "primary": False, "verified": True}],
    ],
)
def test_github_user_without_verified_primary_email_rejected(emails):
    with pytest.raises(GithubAuthError):
        asyncio.run(get_github_user(github_client(emails), "gh-token"))


def test_github_first_login_stores_email(login_github):
    users = InMemoryGithubUsersRepo()
    login_github(users, PRIMARY)
    assert [(u.github_id, u.email, u.password) for u in users.users] == [(7, "octo@example.com", None)]

    login_github(users, PRIMARY)
    assert len(users.users) == 1


def test_github_first_login_after_concurrent_registration_logs_in(login_github):
    # A concurrent first login with the same GitHub account registered it between the checks and the commit
    users = InMemoryGithubUsersRepo()
    winner = User(id=USER_ID, email="octo@example.com", password=None, salt=None, github_id=7)
    tokens = login_github(
        users, PRIMARY, failing_commits=1, concurrent_write=lambda: users.users.append(winner)
    )
    assert decode_token(tokens.access_token, expected_type="access")["userId"] == USER_ID
    assert users.users == [winner]


def test_github_first_login_with_email_taken_meanwhile_raises_user_already_exists(login_github):
    # A concurrent registration took the GitHub email between the checks and the commit
    users = InMemoryGithubUsersRepo()
    winner = User(id=USER_ID, email="octo@example.com", password="x", salt="y", github_id=None)
    with pytest.raises(UserAlreadyExists):
        login_github(users, PRIMARY, failing_commits=1, concurrent_write=lambda: users.users.append(winner))
    assert users.users == [winner]


def test_github_login_leaves_the_stored_email_alone(login_github):
    # The email is taken from GitHub at registration only; a later GitHub email change isn't synced
    users = InMemoryGithubUsersRepo()
    users.users.append(User(id=USER_ID, email=None, password=None, salt=None, github_id=7))
    tokens = login_github(users, PRIMARY)
    assert decode_token(tokens.access_token, expected_type="access")["userId"] == USER_ID
    assert users.users[0].email is None


def test_github_login_with_email_of_password_account_requires_link(login_github):
    users = InMemoryGithubUsersRepo()
    password_user = User(id=USER_ID, email="octo@example.com", password="x", salt="y", github_id=None)
    users.users.append(password_user)

    with pytest.raises(GithubLinkRequired) as exc:
        login_github(users, PRIMARY)
    assert users.users == [password_user]
    assert password_user.github_id is None
    assert exc.value.email == "octo@example.com"
    payload = decode_token(exc.value.pending_link_token, expected_type="github_pending_link")
    assert (payload["userId"], payload["githubId"]) == (USER_ID, 7)


def test_github_login_with_email_of_account_linked_to_other_github(login_github):
    users = InMemoryGithubUsersRepo()
    other = User(id=USER_ID, email="octo@example.com", password=None, salt=None, github_id=99)
    users.users.append(other)

    with pytest.raises(GithubEmailTaken):
        login_github(users, PRIMARY)
    assert users.users == [other]
    assert other.github_id == 99


def _github_router_error(monkeypatch, error: Exception) -> HTTPException:
    async def login_with_github(*args):
        raise error

    monkeypatch.setattr(auth_router.services, "login_with_github", login_with_github)
    client: Any = None
    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth_router.login_github(GithubCode(code="code"), FakeUnitOfWork(), client))
    return exc.value


def test_github_router_account_exists_response(monkeypatch):
    error = _github_router_error(monkeypatch, GithubLinkRequired("octo@example.com", "pending-token"))
    assert error.status_code == 409
    assert isinstance(error.detail, dict)
    assert error.detail["code"] == "ACCOUNT_EXISTS"
    assert error.detail["email"] == "octo@example.com"
    assert error.detail["pending_link_token"] == "pending-token"
    assert error.detail["message"]


@pytest.mark.parametrize("raised", [GithubEmailTaken(), UserAlreadyExists()])
def test_github_router_email_taken_response(monkeypatch, raised):
    # UserAlreadyExists: the email was taken by a concurrent registration after the service's checks
    error = _github_router_error(monkeypatch, raised)
    assert error.status_code == 409
    assert isinstance(error.detail, dict)
    assert error.detail["code"] == "EMAIL_TAKEN"
    assert "pending_link_token" not in error.detail
    assert error.detail["message"]
