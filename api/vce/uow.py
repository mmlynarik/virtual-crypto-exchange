import abc
from typing import Self

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vce.auth.repository import RefreshTokenRepository
from vce.coin.repository import CoinRepository
from vce.user.repository import UsersRepository

UNIQUE_VIOLATION_SQLSTATE = "23505"


class UniqueViolation(Exception):
    """A commit hit a unique constraint, typically because a concurrent request got there first. The
    unit of work has rolled back, so the block can go on, e.g. to look up the row that won."""


class AbstractUnitOfWork(abc.ABC):
    """
    The services' access to storage (see https://www.cosmicpython.com/book/chapter_06_uow). A service
    uses the repositories inside an `async with uow:` block. Every implementation keeps these rules:

    - Nothing is saved until the service calls `await uow.commit()`. Whatever isn't committed when the
      block ends, normally or through an exception, is rolled back.
    - A block can commit more than once. Each commit saves what came before it, and the block can go on,
      e.g. after a `UniqueViolation`.
    - Blocks must not nest. For two separate units of work, use two blocks one after the other.
    """

    users: UsersRepository
    refresh_tokens: RefreshTokenRepository
    coins: CoinRepository

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args) -> None:
        await self.rollback()

    @abc.abstractmethod
    async def commit(self) -> None:
        """When the commit hits a unique constraint it first rolls back and raises UniqueViolation. What that
        means (a taken email, an already linked GitHub account, ...) is for the caller to say."""

    @abc.abstractmethod
    async def rollback(self) -> None:
        """Roll back what wasn't committed. The block can go on using the repositories afterwards."""


class SqlAlchemyUnitOfWork(AbstractUnitOfWork):
    """
    Each block opens a new database session, which all the repositories share. Each commit ends one
    transaction, and the next query starts another. Closing the session at the end of the block rolls back
    the open transaction. Nesting breaks because an inner block would replace the outer block's session
    and repositories, then close them.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

    async def __aenter__(self) -> Self:
        self.session = self.session_factory()
        self.users = UsersRepository(self.session)
        self.refresh_tokens = RefreshTokenRepository(self.session)
        self.coins = CoinRepository(self.session)
        return await super().__aenter__()

    async def __aexit__(self, *args) -> None:
        await self.session.close()

    async def commit(self) -> None:
        """
        Flushes and commits. An IntegrityError with Postgres SQLSTATE 23505 (unique_violation) becomes
        UniqueViolation. Other integrity errors (foreign key, check, not null) are bugs, not races, so they
        are raised as they are. Both roll back first.

        Only the commit translates errors. A query between a write and the commit autoflushes the write,
        and a duplicate then fails in that query as a plain IntegrityError, so services commit right after
        their writes.
        """
        try:
            await self.session.commit()
        except IntegrityError as e:
            await self.rollback()
            if getattr(e.orig, "sqlstate", None) != UNIQUE_VIOLATION_SQLSTATE:
                raise
            raise UniqueViolation from e

    async def rollback(self) -> None:
        await self.session.rollback()
