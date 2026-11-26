import abc
from typing import Self

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vce.auth.repository import RefreshTokenRepository
from vce.coin.repository import CGCoinRepository
from vce.user.repository import UsersRepository

UNIQUE_VIOLATION_SQLSTATE = "23505"


class UniqueViolation(Exception):
    """A commit hit a unique constraint, typically because a concurrent request got there first. The
    unit of work has rolled back, so the block can go on, e.g. to look up the row that won."""


class AbstractUnitOfWork(abc.ABC):
    """
    One database transaction, used as `async with uow:` by a service (see
    https://www.cosmicpython.com/book/chapter_06_uow). The service commits explicitly; anything not committed
    when the block ends is rolled back. A block can commit more than once, each commit ending one transaction.
    Blocks must not nest: each one opens a new session.
    """

    users: UsersRepository
    refresh_tokens: RefreshTokenRepository
    coins: CGCoinRepository

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args) -> None:
        await self.rollback()

    @abc.abstractmethod
    async def commit(self) -> None:
        """Raises UniqueViolation, after rolling back, when the commit hits a unique constraint. What that
        means (a taken email, an already linked GitHub account, ...) is for the caller to say."""

    @abc.abstractmethod
    async def rollback(self) -> None:
        """Roll back what wasn't committed. The block can go on using the repositories afterwards."""


class SqlAlchemyUnitOfWork(AbstractUnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

    async def __aenter__(self) -> Self:
        self.session = self.session_factory()
        self.users = UsersRepository(self.session)
        self.refresh_tokens = RefreshTokenRepository(self.session)
        self.coins = CGCoinRepository(self.session)
        return await super().__aenter__()

    async def __aexit__(self, *args) -> None:
        await self.session.close()

    async def commit(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as e:
            await self.rollback()
            # Other integrity errors (foreign key, check, not null) are bugs, not races: raised as they are
            if getattr(e.orig, "sqlstate", None) != UNIQUE_VIOLATION_SQLSTATE:
                raise
            raise UniqueViolation from e

    async def rollback(self) -> None:
        await self.session.rollback()
