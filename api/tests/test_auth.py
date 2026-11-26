import ast
import asyncio
import inspect
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import jwt
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from vce.auth import router as auth_router
from vce.auth import services
from vce.auth.domain import RefreshToken
from vce.auth.exceptions import (
    GithubAlreadyLinked,
    GithubAuthError,
    GithubEmailTaken,
    GithubLinkRequired,
    InvalidCredentials,
    InvalidToken,
    RefreshTokenReused,
)
from vce.auth.github import get_github_user
from vce.auth.schemas import (
    EmailLoginCredentials,
    EmailRegisterCredentials,
    GithubCode,
    GithubPendingLinkRequest,
)
from vce.auth.security import (
    create_access_token,
    create_github_pending_link_token,
    create_refresh_token,
    decode_token,
)
from vce.settings import (
    EMAIL_MAX_LENGTH,
    GITHUB_EMAILS_URL,
    GITHUB_USER_URL,
    JWT_ALGORITHM,
    JWT_AUDIENCE,
    JWT_SECRET_KEY,
    PASSWORD_MAX_LENGTH,
)
from vce.uow import AbstractUnitOfWork, SqlAlchemyUnitOfWork, UniqueViolation
from vce.user import domain as user_domain
from vce.user.domain import User
from vce.user.exceptions import CannotLinkGithub, UserAlreadyExists, WrongPassword
from vce.utils import hash_password, verify_password

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

USER_ID = uuid.UUID("019a0000-0000-7000-8000-0000000000aa")
FAMILY_ID = uuid.UUID("019a0000-0000-7000-8000-000000000001")


def test_access_token_roundtrip():
    payload = decode_token(create_access_token(USER_ID), expected_type="access")
    assert payload["userId"] == USER_ID
    assert payload["aud"] == JWT_AUDIENCE


def test_refresh_token_roundtrip():
    record = create_refresh_token(USER_ID, FAMILY_ID)
    assert record.token is not None
    payload = decode_token(record.token, expected_type="refresh")
    assert payload["jti"] == record.jti
    assert payload["fam"] == FAMILY_ID
    assert record.family_id == FAMILY_ID
    assert record.user_id == USER_ID
    assert payload["userId"] == USER_ID


@pytest.mark.parametrize("claim", ["userId", "jti", "fam"])
@pytest.mark.parametrize("value", ["not-a-uuid", 123])
def test_malformed_refresh_uuid_claims_rejected(claim, value):
    claims: dict[str, Any] = {"type": "refresh", "jti": str(uuid.uuid7()), "fam": str(FAMILY_ID)}
    claims[claim] = value
    with pytest.raises(InvalidToken):
        decode_token(_encode(**claims), expected_type="refresh")


def test_access_token_with_integer_user_id_rejected():
    # Tokens issued before user ids became UUIDs
    with pytest.raises(InvalidToken):
        decode_token(_encode(userId=42), expected_type="access")


def test_token_type_is_enforced():
    refresh = create_refresh_token(USER_ID, FAMILY_ID).token
    assert refresh is not None
    with pytest.raises(InvalidToken):
        decode_token(refresh, expected_type="access")
    with pytest.raises(InvalidToken):
        decode_token(create_access_token(USER_ID), expected_type="refresh")


GITHUB_ID = 12345678


def test_github_pending_link_token_roundtrip():
    payload = decode_token(
        create_github_pending_link_token(USER_ID, GITHUB_ID), expected_type="github_pending_link"
    )
    assert payload["userId"] == USER_ID
    assert payload["githubId"] == GITHUB_ID


def test_github_pending_link_token_type_is_enforced():
    pending = create_github_pending_link_token(USER_ID, GITHUB_ID)
    with pytest.raises(InvalidToken):
        decode_token(pending, expected_type="access")
    with pytest.raises(InvalidToken):
        decode_token(pending, expected_type="refresh")

    refresh = create_refresh_token(USER_ID, FAMILY_ID).token
    assert refresh is not None
    for other in (create_access_token(USER_ID), refresh):
        with pytest.raises(InvalidToken):
            decode_token(other, expected_type="github_pending_link")


def test_github_pending_link_token_without_github_id_rejected():
    with pytest.raises(InvalidToken):
        decode_token(_encode(type="github_pending_link"), expected_type="github_pending_link")


@pytest.mark.parametrize("value", ["12345678", 1.5, True, None])
def test_github_pending_link_token_non_int_github_id_rejected(value):
    with pytest.raises(InvalidToken):
        decode_token(_encode(type="github_pending_link", githubId=value), expected_type="github_pending_link")


def test_github_pending_link_token_malformed_user_id_rejected():
    with pytest.raises(InvalidToken):
        decode_token(
            _encode(type="github_pending_link", githubId=GITHUB_ID, userId="not-a-uuid"),
            expected_type="github_pending_link",
        )


def _encode(**overrides):
    now = datetime.now(UTC)
    claims = {
        "userId": str(USER_ID),
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
        {"userId": str(USER_ID), "type": "access", "aud": JWT_AUDIENCE}, "other-secret", algorithm="HS256"
    )
    with pytest.raises(InvalidToken):
        decode_token(token, expected_type="access")


# --- rotation & revocation (services with in-memory fakes) ---


class FakeTokenRepo:
    def __init__(self):
        self.rows: dict[uuid.UUID, RefreshToken] = {}

    async def add(self, token: RefreshToken):
        self.rows[token.jti] = token

    async def consume(self, jti: uuid.UUID) -> RefreshToken | None:
        return self.rows.pop(jti, None)

    async def revoke_family(self, family_id: uuid.UUID):
        self.rows = {k: v for k, v in self.rows.items() if v.family_id != family_id}

    async def delete_expired_for_user(self, user_id: uuid.UUID):
        now = datetime.now(UTC)
        self.rows = {k: v for k, v in self.rows.items() if not (v.user_id == user_id and v.expires_at < now)}

    def families(self) -> set[uuid.UUID]:
        return {r.family_id for r in self.rows.values()}


class FakeUsersRepo:
    async def get_by_id(self, id: uuid.UUID) -> User | None:
        return User(id=id, email="a@b.c", password=None, salt=None, github_id=None)


class FakeUnitOfWork(AbstractUnitOfWork):
    """In-memory stand-in. Counts commits; the first failing_commits of them fail like a unique constraint
    that a concurrent request got to first."""

    # The in-memory fakes, not the SQLAlchemy repositories
    users: Any
    refresh_tokens: Any

    def __init__(self, users: Any = None, refresh_tokens: Any = None, failing_commits: int = 0):
        self.users = users if users is not None else InMemoryGithubUsersRepo()
        self.refresh_tokens = refresh_tokens if refresh_tokens is not None else FakeTokenRepo()
        self.failing_commits = failing_commits
        self.commits = 0

    async def commit(self):
        if self.failing_commits:
            self.failing_commits -= 1
            raise UniqueViolation
        self.commits += 1

    async def rollback(self):
        pass


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


# --- email availability ---


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


# --- registration races and input limits ---


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


# --- case-insensitive emails ---


def test_emails_are_lowercased():
    assert (
        EmailRegisterCredentials(email="John.Doe@Gmail.COM", password="password").email
        == "john.doe@gmail.com"
    )
    assert EmailLoginCredentials(email=" JOHN.DOE@gmail.com ", password="x").email == "john.doe@gmail.com"


class InMemoryUsersRepo:
    """Matches emails exactly, like the database does."""

    def __init__(self):
        self.users: list[User] = []

    async def get_by_email(self, email: str) -> User | None:
        return next((u for u in self.users if u.email == email), None)

    async def get_by_id(self, id: uuid.UUID) -> User | None:
        return next((u for u in self.users if u.id == id), None)

    async def add(self, user: User):
        self.users.append(user)

    async def lock(self, user: User):
        pass


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


# --- GitHub login ---


def _github_client(emails: list[dict[str, Any]], github_id: int = 7) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == GITHUB_USER_URL:
            return httpx.Response(
                200, json={"id": github_id, "login": "octocat", "name": None, "email": None}
            )
        if url == GITHUB_EMAILS_URL:
            return httpx.Response(200, json=emails)
        return httpx.Response(404)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_github_user_uses_primary_verified_email():
    client = _github_client(
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
        asyncio.run(get_github_user(_github_client(emails), "gh-token"))


class InMemoryGithubUsersRepo(InMemoryUsersRepo):
    async def get_by_github_id(self, github_id: int) -> User | None:
        return next((u for u in self.users if u.github_id == github_id), None)


@pytest.fixture
def login_github(monkeypatch):
    async def exchange_code_for_token(client, code):
        return "gh-token"

    monkeypatch.setattr(services, "exchange_code_for_token", exchange_code_for_token)

    def login(users, emails, github_id=7, failing_commits=0):
        client = _github_client(emails, github_id)
        uow = FakeUnitOfWork(users=users, failing_commits=failing_commits)
        return asyncio.run(services.login_with_github("code", uow, client))

    return login


PRIMARY = [{"email": "Octo@Example.com", "primary": True, "verified": True}]


def test_github_first_login_stores_email(login_github):
    users = InMemoryGithubUsersRepo()
    login_github(users, PRIMARY)
    assert [(u.github_id, u.email, u.password) for u in users.users] == [(7, "octo@example.com", None)]

    login_github(users, PRIMARY)
    assert len(users.users) == 1


def test_github_first_login_after_concurrent_registration_logs_in(login_github):
    # A concurrent first login with the same GitHub account registered it between the checks and the commit
    users = InMemoryGithubUsersRepo()
    tokens = login_github(users, PRIMARY, failing_commits=1)
    assert decode_token(tokens.access_token, expected_type="access")["userId"] == users.users[0].id


class RejectingUsersRepo(InMemoryGithubUsersRepo):
    """Registrations never land, as when the database rejects the insert."""

    async def add(self, user: User):
        pass


def test_github_first_login_with_email_taken_meanwhile_raises_user_already_exists(login_github):
    # A concurrent registration took the GitHub email between the checks and the commit
    with pytest.raises(UserAlreadyExists):
        login_github(RejectingUsersRepo(), PRIMARY, failing_commits=1)


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


@pytest.mark.parametrize(
    "password, github_id, expected",
    [("x", None, True), ("x", 99, False), (None, None, False), (None, 99, False)],
)
def test_user_can_link_github(password, github_id, expected):
    salt = "y" if password else None
    user = User(id=USER_ID, email="a@b.c", password=password, salt=salt, github_id=github_id)
    assert user.can_link_github is expected


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


# --- linking GitHub to an existing account ---


def test_user_from_password():
    user = User.from_password(email="a@example.com", password="correct horse")
    assert (user.email, user.github_id) == ("a@example.com", None)
    assert user.id.version == 7
    # Stored hashed and salted: the same password gets another hash for another user
    assert user.password not in (None, "correct horse")
    assert user.password != User.from_password(email="b@example.com", password="correct horse").password
    user.check_password("correct horse")
    with pytest.raises(WrongPassword):
        user.check_password("wrong horse")


def test_user_from_github():
    user = User.from_github(github_id=GITHUB_ID, email="octo@example.com")
    assert (user.github_id, user.email, user.password, user.salt) == (
        GITHUB_ID,
        "octo@example.com",
        None,
        None,
    )
    assert user.id.version == 7
    assert User.from_github(github_id=GITHUB_ID, email="octo@example.com").id != user.id


def test_user_link_github_sets_github_id():
    user = User(id=USER_ID, email="octo@example.com", password="x", salt="y", github_id=None)
    user.link_github(GITHUB_ID)
    assert user.github_id == GITHUB_ID


@pytest.mark.parametrize("password, github_id", [("x", 99), (None, None)], ids=["linked", "no-password"])
def test_user_link_github_rejected_when_it_cannot_link(password, github_id):
    salt = "y" if password else None
    user = User(id=USER_ID, email="octo@example.com", password=password, salt=salt, github_id=github_id)
    with pytest.raises(CannotLinkGithub):
        user.link_github(GITHUB_ID)
    assert user.github_id == github_id


def test_user_check_password():
    user = User(id=USER_ID, email="a@b.c", password=NODE_HASH, salt=NODE_SALT, github_id=None)
    user.check_password("pässword 123")  # doesn't raise
    with pytest.raises(WrongPassword):
        user.check_password("wrong password")


def test_user_without_password_rejects_any_password():
    user = User(id=USER_ID, email="a@b.c", password=None, salt=None, github_id=7)
    with pytest.raises(WrongPassword):
        user.check_password("")


def test_user_domain_does_not_depend_on_auth():
    # Auth builds on users, not the other way round: auth translates the user errors (WrongPassword,
    # CannotLinkGithub) into its own
    tree = ast.parse(inspect.getsource(user_domain))
    imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not [m for m in imported if m.split(".")[:2] == ["vce", "auth"]]


# --- redeeming the pending link token with the account's password ---

NODE_PASSWORD = "pässword 123"  # matches NODE_HASH with NODE_SALT


def _password_user(github_id: int | None = None) -> User:
    return User(id=USER_ID, email="octo@example.com", password=NODE_HASH, salt=NODE_SALT, github_id=github_id)


def _link_pending(uow: FakeUnitOfWork, token: str, password: str = NODE_PASSWORD):
    return asyncio.run(services.link_github_with_password(token, password, uow))


def test_link_pending_links_github_and_logs_in(login_github):
    users = InMemoryGithubUsersRepo()
    user = _password_user()
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
    user = _password_user()
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
        lambda: _encode(type="github_pending_link", githubId=7, exp=datetime.now(UTC) - timedelta(seconds=1)),
        lambda: create_github_pending_link_token(USER_ID, 7)[:-2] + "xx",
        lambda: create_access_token(USER_ID),
    ],
    ids=["expired", "tampered", "access-token"],
)
def test_link_pending_with_invalid_token_rejected(token):
    uow = FakeUnitOfWork()
    user = _password_user()
    uow.users.users.append(user)
    with pytest.raises(InvalidToken):
        _link_pending(uow, token())
    assert user.github_id is None


def test_link_pending_when_account_got_github_meanwhile_rejected():
    uow = FakeUnitOfWork()
    uow.users.users.append(_password_user(github_id=99))
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
    users.users.append(_password_user())
    uow = FakeUnitOfWork(users=users)
    with pytest.raises(GithubAlreadyLinked):
        _link_pending(uow, create_github_pending_link_token(USER_ID, 7))
    assert users.users[0].github_id == 99
    assert uow.commits == 0


def test_link_pending_when_github_id_now_on_another_account_rejected():
    uow = FakeUnitOfWork()
    user = _password_user()
    uow.users.users.append(user)
    uow.users.users.append(User(id=uuid.uuid7(), email=None, password=None, salt=None, github_id=7))
    with pytest.raises(GithubAlreadyLinked):
        _link_pending(uow, create_github_pending_link_token(USER_ID, 7))
    assert user.github_id is None


def test_link_pending_when_github_id_taken_before_commit_rejected():
    # The same GitHub id was linked to or registered as another account between the check and the commit
    uow = FakeUnitOfWork(failing_commits=1)
    uow.users.users.append(_password_user())
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


# --- current user ---


def test_user_from_access_token():
    uow = FakeUnitOfWork()
    user = _password_user()
    uow.users.users.append(user)
    assert asyncio.run(services.get_user_from_access_token(create_access_token(USER_ID), uow)) is user
    assert uow.commits == 0


def test_user_from_access_token_of_deleted_user_rejected():
    with pytest.raises(InvalidToken):
        asyncio.run(services.get_user_from_access_token(create_access_token(USER_ID), FakeUnitOfWork()))


# --- SQLAlchemy unit of work ---


class DriverError(Exception):
    """Like asyncpg's errors as SQLAlchemy wraps them: they carry the Postgres SQLSTATE."""

    def __init__(self, sqlstate: str):
        super().__init__(f"SQLSTATE {sqlstate}")
        self.sqlstate = sqlstate


class RecordingSession:
    def __init__(self, failing_sqlstate: str | None = None):
        self.calls: list[str] = []
        self.failing_sqlstate = failing_sqlstate

    async def commit(self):
        self.calls.append("commit")
        if self.failing_sqlstate:
            raise IntegrityError("INSERT INTO user ...", {}, DriverError(self.failing_sqlstate))

    async def rollback(self):
        self.calls.append("rollback")

    async def close(self):
        self.calls.append("close")


def test_sqlalchemy_uow_opens_a_session_per_block_and_closes_it():
    sessions: list[RecordingSession] = []

    def session_factory():
        sessions.append(RecordingSession())
        return sessions[-1]

    factory: Any = session_factory
    uow = SqlAlchemyUnitOfWork(factory)

    async def use():
        async with uow:
            assert uow.users.session is uow.refresh_tokens.session is sessions[-1]
            await uow.commit()
        with pytest.raises(RuntimeError):
            async with uow:
                raise RuntimeError

    asyncio.run(use())
    # close() rolls back what wasn't committed without expiring the loaded objects (rollback() would), so a
    # User read in the block stays readable after it, e.g. by /auth/me
    assert [s.calls for s in sessions] == [["commit", "close"], ["close"]]


def _commit_failing_with(sqlstate: str, expected: type[Exception]) -> RecordingSession:
    session = RecordingSession(failing_sqlstate=sqlstate)
    factory: Any = lambda: session
    uow = SqlAlchemyUnitOfWork(factory)

    async def use():
        async with uow:
            with pytest.raises(expected):
                await uow.commit()
            # Rolled back, so the block can go on using the session, e.g. to look up who got there first
            assert session.calls == ["commit", "rollback"]

    asyncio.run(use())
    return session


def test_sqlalchemy_uow_rolls_back_a_commit_that_hits_a_unique_constraint():
    session = _commit_failing_with("23505", UniqueViolation)
    assert session.calls == ["commit", "rollback", "close"]


def test_sqlalchemy_uow_raises_other_integrity_errors_as_they_are():
    # e.g. ck_user_email_lowercase: a bug to surface, not a race to report as "already exists"
    _commit_failing_with("23514", IntegrityError)
