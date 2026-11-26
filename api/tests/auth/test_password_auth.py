"""Registering and logging in with an email and password, and email availability."""

import asyncio

import pytest
from pydantic import ValidationError

from tests.fakes import (
    USER_ID,
    FakeUnitOfWork,
    InMemoryUsersRepo,
)
from vce.auth import services
from vce.auth.schemas import (
    EmailLoginCredentials,
    EmailRegisterCredentials,
)
from vce.settings import (
    EMAIL_MAX_LENGTH,
    PASSWORD_MAX_LENGTH,
)
from vce.user.domain import User
from vce.user.exceptions import UserAlreadyExists


class FakeEmailUsersRepo:
    async def get_by_email(self, email: str) -> User | None:
        if email == "taken@example.com":
            return User(id=USER_ID, email=email, password="x", salt="y", github_id=None)
        return None


def test_email_available():
    uow = FakeUnitOfWork(users=FakeEmailUsersRepo())
    assert asyncio.run(services.is_email_available("free@example.com", uow))
    assert not asyncio.run(services.is_email_available("taken@example.com", uow))
    assert uow.commits == 0


def test_register_creates_user_and_session_in_one_transaction():
    uow = FakeUnitOfWork()
    register = EmailRegisterCredentials(email="a@example.com", password="correct horse")
    response = asyncio.run(services.register_with_password(register, uow))
    assert [u.id for u in uow.users.users] == [response.user_id]
    assert len(uow.refresh_tokens.rows) == 1
    assert uow.commits == 1


def test_concurrent_registration_raises_user_already_exists():
    # A concurrent registration inserted the same email between the existence check and the commit
    uow = FakeUnitOfWork(failing_commits=1)
    register = EmailRegisterCredentials(email="a@example.com", password="correct horse")
    with pytest.raises(UserAlreadyExists):
        asyncio.run(services.register_with_password(register, uow))
    assert uow.commits == 0


def test_credentials_length_limits():
    with pytest.raises(ValidationError):
        EmailRegisterCredentials(email="a@example.com", password="x" * (PASSWORD_MAX_LENGTH + 1))
    with pytest.raises(ValidationError):
        EmailLoginCredentials(email="a" * EMAIL_MAX_LENGTH + "@example.com", password="password")
    EmailRegisterCredentials(email="a@example.com", password="x" * PASSWORD_MAX_LENGTH)


def test_emails_are_lowercased():
    assert (
        EmailRegisterCredentials(email="John.Doe@Gmail.COM", password="password").email
        == "john.doe@gmail.com"
    )
    assert EmailLoginCredentials(email=" JOHN.DOE@gmail.com ", password="x").email == "john.doe@gmail.com"


def test_register_and_login_with_different_case():
    users = InMemoryUsersRepo()
    uow = FakeUnitOfWork(users=users)
    register = EmailRegisterCredentials(email="John.Doe@Gmail.COM", password="correct horse")
    asyncio.run(services.register_with_password(register, uow))
    assert users.users[0].email == "john.doe@gmail.com"

    for typed in ("john.doe@gmail.com", "JOHN.DOE@GMAIL.COM"):
        login = EmailLoginCredentials(email=typed, password="correct horse")
        assert asyncio.run(services.login_with_password(login, uow)).access_token

    assert not asyncio.run(
        services.is_email_available(
            EmailRegisterCredentials(email="JOHN.doe@gmail.com", password="password").email, uow
        )
    )
