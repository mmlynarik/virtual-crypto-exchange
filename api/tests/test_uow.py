"""The SQLAlchemy unit of work."""

import asyncio
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError

from vce.uow import SqlAlchemyUnitOfWork, UniqueViolation


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
