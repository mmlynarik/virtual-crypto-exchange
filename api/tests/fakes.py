"""Fakes, constants and helpers shared by the test modules."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import jwt

from vce.auth.domain import RefreshToken
from vce.settings import (
    GITHUB_EMAILS_URL,
    GITHUB_USER_URL,
    JWT_ALGORITHM,
    JWT_AUDIENCE,
    JWT_SECRET_KEY,
)
from vce.uow import AbstractUnitOfWork, UniqueViolation
from vce.user.domain import User

# Generated with Node (same call as web/src/lib/auth/passwordHasher.ts):
# crypto.scrypt("pässword 123".normalize(), "a1b2c3d4e5f60718293a4b5c6d7e8f90", 64)
NODE_SALT = "a1b2c3d4e5f60718293a4b5c6d7e8f90"
NODE_HASH = (
    "438f15f9f77ccfb490cd07a576d1c0992a6ce3d93a0f8507973d2347b27f3693"
    "0ee8d8290bddc7fee9a3618278a75fbb8672f6c77578412e4cb6f799e8e5f846"
)
NODE_PASSWORD = "pässword 123"  # matches NODE_HASH with NODE_SALT

USER_ID = uuid.UUID("019a0000-0000-7000-8000-0000000000aa")
FAMILY_ID = uuid.UUID("019a0000-0000-7000-8000-000000000001")
GITHUB_ID = 12345678

# The GitHub emails of a user with one primary, verified address
PRIMARY = [{"email": "Octo@Example.com", "primary": True, "verified": True}]


def encode_token(**overrides):
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


def github_client(emails: list[dict[str, Any]], github_id: int = 7) -> httpx.AsyncClient:
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


class InMemoryGithubUsersRepo(InMemoryUsersRepo):
    async def get_by_github_id(self, github_id: int) -> User | None:
        return next((u for u in self.users if u.github_id == github_id), None)


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


def password_user(github_id: int | None = None) -> User:
    return User(id=USER_ID, email="octo@example.com", password=NODE_HASH, salt=NODE_SALT, github_id=github_id)
