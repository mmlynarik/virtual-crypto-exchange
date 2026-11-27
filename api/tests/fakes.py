"""Fakes, constants and helpers shared by the test modules."""

import copy
import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Self

import httpx
import jwt

from vce.auth.domain import RefreshToken
from vce.coin.domain import Coin
from vce.settings import (
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
        if request.url.path == "/user":
            return httpx.Response(
                200, json={"id": github_id, "login": "octocat", "name": None, "email": None}
            )
        if request.url.path == "/user/emails":
            return httpx.Response(200, json=emails)
        return httpx.Response(404)

    return httpx.AsyncClient(base_url="https://github.test", transport=httpx.MockTransport(handler))


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


class InMemoryCoinRepo:
    def __init__(self):
        self.coins: dict[str, Coin] = {}

    async def add(self, coin: Coin):
        self.coins[coin.id] = coin

    async def exists(self, symbol: str) -> bool:
        return any(c.symbol == symbol for c in self.coins.values())

    async def get_by_symbol(self, symbol: str) -> list[Coin]:
        return [c for c in self.coins.values() if c.symbol == symbol]

    async def get_by_id(self, id: str) -> Coin | None:
        return self.coins.get(id)

    async def list(self) -> list[Coin]:
        return list(self.coins.values())

    async def delete(self, id: str):
        del self.coins[id]

    async def update_market_data(self, coins: Sequence[Coin]):
        for coin in coins:
            stored = self.coins[coin.id]
            for field in MARKET_FIELDS:
                setattr(stored, field, getattr(coin, field))


# What CoinRepository.update_market_data updates: name and symbol stay
MARKET_FIELDS = [
    "current_price",
    "market_cap",
    "circulating_supply",
    "total_supply",
    "max_supply",
    "last_updated",
]


# The repositories with their attributes, and the rows with their fields
type _Snapshot = tuple[list[tuple[Any, dict[str, Any]]], list[tuple[Any, dict[str, Any]]]]


class FakeUnitOfWork(AbstractUnitOfWork):
    """
    In-memory stand-in that keeps the AbstractUnitOfWork rules: what a block doesn't commit is rolled back,
    on the same objects, as SQLAlchemy reloads them. Counts commits. The first failing_commits of them roll
    back and fail like a unique constraint that a concurrent request got to first; concurrent_write is that
    request's committed write, applied at the first failing commit.
    """

    # The in-memory fakes, not the SQLAlchemy repositories
    users: Any
    refresh_tokens: Any
    coins: Any

    def __init__(
        self,
        users: Any = None,
        refresh_tokens: Any = None,
        coins: Any = None,
        failing_commits: int = 0,
        concurrent_write: Callable[[], None] | None = None,
    ):
        self.users = users if users is not None else InMemoryGithubUsersRepo()
        self.refresh_tokens = refresh_tokens if refresh_tokens is not None else FakeTokenRepo()
        self.coins = coins if coins is not None else InMemoryCoinRepo()
        self.failing_commits = failing_commits
        self.concurrent_write = concurrent_write
        self.commits = 0

    async def __aenter__(self) -> Self:
        self._committed = self._snapshot()
        return await super().__aenter__()

    async def commit(self):
        if self.failing_commits:
            self.failing_commits -= 1
            await self.rollback()
            if self.concurrent_write:
                self.commit_concurrent_write(self.concurrent_write)
                self.concurrent_write = None
            raise UniqueViolation
        self.commits += 1
        self._committed = self._snapshot()

    async def rollback(self):
        self._restore(self._committed)

    def commit_concurrent_write(self, write: Callable[[], None]) -> None:
        """Apply a write that a concurrent request committed, so this block's rollback keeps it. Only where
        the block has nothing uncommitted, which would be kept too."""
        write()
        self._committed = self._snapshot()

    def _repos(self) -> list[Any]:
        return [self.users, self.refresh_tokens, self.coins]

    def _snapshot(self) -> _Snapshot:
        """The repositories' attributes, with their lists and dicts of rows copied, and each row's fields."""
        repos = []
        rows = {}
        for repo in self._repos():
            state = {}
            for name, value in vars(repo).items():
                if isinstance(value, list | dict):
                    state[name] = copy.copy(value)
                    for row in value.values() if isinstance(value, dict) else value:
                        rows[id(row)] = (row, dict(vars(row)))
                else:
                    state[name] = value
            repos.append((repo, state))
        return repos, list(rows.values())

    @staticmethod
    def _restore(snapshot: _Snapshot) -> None:
        repos, rows = snapshot
        for repo, state in repos:
            repo.__dict__.clear()
            repo.__dict__.update({name: copy.copy(value) for name, value in state.items()})
        for row, fields in rows:
            row.__dict__.clear()
            row.__dict__.update(fields)


def password_user(github_id: int | None = None) -> User:
    return User(id=USER_ID, email="octo@example.com", password=NODE_HASH, salt=NODE_SALT, github_id=github_id)
