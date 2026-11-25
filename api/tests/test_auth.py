import asyncio
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
    hash_password,
    verify_password,
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
from vce.user import services as user_services
from vce.user.domain import User
from vce.user.exceptions import UserAlreadyExists
from vce.user.schemas import UserCreateByEmail

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


class FakeSession:
    async def commit(self):
        pass


@pytest.fixture
def ctx():
    return FakeUsersRepo(), FakeTokenRepo(), FakeSession()


def _start(ctx, user_id=USER_ID):
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
    assert decode_token(second.access_token, "access")["userId"] == USER_ID


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


# --- email availability ---


class FakeEmailUsersRepo:
    async def get_by_email(self, email: str) -> User | None:
        if email == "taken@example.com":
            return User(id=USER_ID, email=email, password="x", salt="y", github_id=None)
        return None


def test_email_available():
    users: Any = FakeEmailUsersRepo()
    assert asyncio.run(services.is_email_available("free@example.com", users))
    assert not asyncio.run(services.is_email_available("taken@example.com", users))


# --- registration races and input limits ---


class FakeEmptyUsersRepo:
    """No user exists yet, so the services' existence check passes."""

    def __init__(self):
        self.added: list[User] = []

    async def get_by_email(self, email: str) -> User | None:
        return None

    async def get_by_github_id(self, github_id: int) -> User | None:
        return None

    async def add(self, user: User):
        self.added.append(user)


class UniqueViolationSession:
    """Behaves like the database when a concurrent registration inserted the same user first."""

    def __init__(self):
        self.rolled_back = False

    async def commit(self):
        raise IntegrityError(
            "INSERT INTO user ...", {}, Exception("duplicate key value violates unique constraint")
        )

    async def rollback(self):
        self.rolled_back = True


def test_concurrent_registration_raises_user_already_exists():
    users: Any = FakeEmptyUsersRepo()
    session: Any = UniqueViolationSession()
    user_create = UserCreateByEmail(email="a@example.com", password="hash", salt="salt")
    with pytest.raises(UserAlreadyExists):
        asyncio.run(user_services.register_user_by_email(user_create, users, session))
    assert session.rolled_back


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


class NoopSession:
    async def commit(self):
        pass


def test_register_and_login_with_different_case():
    # Typed as Any: in-memory stand-ins for the repositories and the session
    users: Any = InMemoryUsersRepo()
    tokens: Any = FakeTokenRepo()
    session: Any = NoopSession()
    register = EmailRegisterCredentials(email="John.Doe@Gmail.COM", password="correct horse")
    asyncio.run(services.register_with_password(register, users, tokens, session))
    assert users.users[0].email == "john.doe@gmail.com"

    for typed in ("john.doe@gmail.com", "JOHN.DOE@GMAIL.COM"):
        login = EmailLoginCredentials(email=typed, password="correct horse")
        assert asyncio.run(services.login_with_password(login, users, tokens, session)).access_token

    assert not asyncio.run(
        services.is_email_available(
            EmailRegisterCredentials(email="JOHN.doe@gmail.com", password="password").email, users
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

    def login(users, emails, github_id=7):
        client = _github_client(emails, github_id)
        tokens: Any = FakeTokenRepo()
        session: Any = NoopSession()
        return asyncio.run(services.login_with_github("code", users, tokens, session, client))

    return login


PRIMARY = [{"email": "Octo@Example.com", "primary": True, "verified": True}]


def test_github_first_login_stores_email(login_github):
    users: Any = InMemoryGithubUsersRepo()
    login_github(users, PRIMARY)
    assert [(u.github_id, u.email, u.password) for u in users.users] == [(7, "octo@example.com", None)]

    login_github(users, PRIMARY)
    assert len(users.users) == 1


def test_github_login_fills_missing_email(login_github):
    users: Any = InMemoryGithubUsersRepo()
    users.users.append(User(id=USER_ID, email=None, password=None, salt=None, github_id=7))
    login_github(users, PRIMARY)
    assert users.users[0].email == "octo@example.com"


def test_github_login_with_email_of_password_account_requires_link(login_github):
    users: Any = InMemoryGithubUsersRepo()
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
    users: Any = InMemoryGithubUsersRepo()
    other = User(id=USER_ID, email="octo@example.com", password=None, salt=None, github_id=99)
    users.users.append(other)

    with pytest.raises(GithubEmailTaken):
        login_github(users, PRIMARY)
    assert users.users == [other]
    assert other.github_id == 99


def test_github_user_without_email_does_not_take_email_of_another_account(login_github):
    # A GitHub user registered before emails were stored keeps logging in, without the taken email
    users: Any = InMemoryGithubUsersRepo()
    users.users.append(
        User(id=uuid.uuid7(), email="octo@example.com", password="x", salt="y", github_id=None)
    )
    users.users.append(User(id=USER_ID, email=None, password=None, salt=None, github_id=7))
    login_github(users, PRIMARY)
    assert users.users[1].email is None


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
    session: Any = NoopSession()
    client: Any = None
    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth_router.login_github(GithubCode(code="code"), session, client))
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


def test_link_github_sets_github_id():
    user = User(id=USER_ID, email="octo@example.com", password="x", salt="y", github_id=None)
    session: Any = NoopSession()
    asyncio.run(user_services.link_github(user, GITHUB_ID, session))
    assert user.github_id == GITHUB_ID


def test_concurrent_link_github_raises_user_already_exists():
    # The same GitHub id was linked to or registered as another account between the caller's check and commit
    user = User(id=USER_ID, email="octo@example.com", password="x", salt="y", github_id=None)
    session: Any = UniqueViolationSession()
    with pytest.raises(UserAlreadyExists):
        asyncio.run(user_services.link_github(user, GITHUB_ID, session))
    assert session.rolled_back


# --- redeeming the pending link token with the account's password ---

NODE_PASSWORD = "pässword 123"  # matches NODE_HASH with NODE_SALT


def _password_user(github_id: int | None = None) -> User:
    return User(id=USER_ID, email="octo@example.com", password=NODE_HASH, salt=NODE_SALT, github_id=github_id)


def _link_pending(users, token: str, password: str = NODE_PASSWORD):
    tokens: Any = FakeTokenRepo()
    session: Any = NoopSession()
    return asyncio.run(services.link_github_with_password(token, password, users, tokens, session))


def test_link_pending_links_github_and_logs_in(login_github):
    users: Any = InMemoryGithubUsersRepo()
    user = _password_user()
    users.users.append(user)

    tokens = _link_pending(users, create_github_pending_link_token(USER_ID, 7))
    assert decode_token(tokens.access_token, expected_type="access")["userId"] == USER_ID
    assert user.github_id == 7

    # The next GitHub login finds the account by its GitHub id, and password login still works
    tokens = login_github(users, PRIMARY)
    assert decode_token(tokens.access_token, expected_type="access")["userId"] == USER_ID
    assert users.users == [user]
    login = EmailLoginCredentials(email="octo@example.com", password=NODE_PASSWORD)
    tokens_repo: Any = FakeTokenRepo()
    session: Any = NoopSession()
    assert asyncio.run(services.login_with_password(login, users, tokens_repo, session)).access_token


def test_link_pending_with_wrong_password_rejected():
    users: Any = InMemoryGithubUsersRepo()
    user = _password_user()
    users.users.append(user)
    with pytest.raises(InvalidCredentials):
        _link_pending(users, create_github_pending_link_token(USER_ID, 7), password="wrong password")
    assert user.github_id is None


def test_link_pending_for_deleted_user_rejected():
    users: Any = InMemoryGithubUsersRepo()
    with pytest.raises(InvalidCredentials):
        _link_pending(users, create_github_pending_link_token(USER_ID, 7))


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
    users: Any = InMemoryGithubUsersRepo()
    user = _password_user()
    users.users.append(user)
    with pytest.raises(InvalidToken):
        _link_pending(users, token())
    assert user.github_id is None


def test_link_pending_when_account_got_github_meanwhile_rejected():
    users: Any = InMemoryGithubUsersRepo()
    users.users.append(_password_user(github_id=99))
    with pytest.raises(GithubAlreadyLinked):
        _link_pending(users, create_github_pending_link_token(USER_ID, 7))
    assert users.users[0].github_id == 99


def test_link_pending_when_github_id_now_on_another_account_rejected():
    users: Any = InMemoryGithubUsersRepo()
    user = _password_user()
    users.users.append(user)
    users.users.append(User(id=uuid.uuid7(), email=None, password=None, salt=None, github_id=7))
    with pytest.raises(GithubAlreadyLinked):
        _link_pending(users, create_github_pending_link_token(USER_ID, 7))
    assert user.github_id is None


@pytest.mark.parametrize(
    "raised, status",
    [
        (InvalidToken("expired"), 401),
        (InvalidCredentials(), 401),
        (GithubAlreadyLinked(), 409),
        (UserAlreadyExists(), 409),
    ],
)
def test_link_pending_router_errors(monkeypatch, raised, status):
    async def link_github_with_password(*args):
        raise raised

    monkeypatch.setattr(auth_router.services, "link_github_with_password", link_github_with_password)
    session: Any = NoopSession()
    body = GithubPendingLinkRequest(pending_link_token="token", password="password")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth_router.link_github_pending(body, session))
    assert exc.value.status_code == status


def test_link_pending_request_password_length_limit():
    with pytest.raises(ValidationError):
        GithubPendingLinkRequest(pending_link_token="token", password="x" * (PASSWORD_MAX_LENGTH + 1))
