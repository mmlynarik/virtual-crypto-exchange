"""FakeUnitOfWork keeps the AbstractUnitOfWork rules, so service tests catch a missing commit."""

import asyncio

import pytest

from tests.fakes import FakeUnitOfWork, password_user
from vce.uow import UniqueViolation


def test_uncommitted_add_is_rolled_back_when_the_block_ends():
    uow = FakeUnitOfWork()

    async def main():
        async with uow:
            await uow.users.add(password_user())

    asyncio.run(main())
    assert uow.users.users == []


def test_uncommitted_change_is_rolled_back_on_the_same_object():
    user = password_user()
    uow = FakeUnitOfWork()
    uow.users.users.append(user)

    async def main():
        async with uow:
            user.link_github(7)

    asyncio.run(main())
    assert uow.users.users == [user]
    assert user.github_id is None


def test_rollback_on_exception():
    user = password_user()
    uow = FakeUnitOfWork()
    uow.users.users.append(user)

    async def main():
        async with uow:
            user.link_github(7)
            raise RuntimeError

    with pytest.raises(RuntimeError):
        asyncio.run(main())
    assert user.github_id is None


def test_committed_changes_survive_a_later_rollback():
    user = password_user()
    uow = FakeUnitOfWork()

    async def main():
        async with uow:
            await uow.users.add(user)
            await uow.commit()
            user.link_github(7)

    asyncio.run(main())
    assert uow.users.users == [user]
    assert user.github_id is None
    assert uow.commits == 1


def test_failing_commit_rolls_back_then_applies_the_concurrent_write():
    winner = password_user(github_id=7)
    uow = FakeUnitOfWork(failing_commits=1, concurrent_write=lambda: uow.users.users.append(winner))

    async def main():
        async with uow:
            await uow.users.add(password_user())
            with pytest.raises(UniqueViolation):
                await uow.commit()
            assert uow.users.users == [winner]

    asyncio.run(main())
    # The concurrent request's write was committed, so this block's rollback keeps it
    assert uow.users.users == [winner]
    assert uow.commits == 0


def test_concurrent_commit_survives_the_blocks_rollback():
    user = password_user()
    uow = FakeUnitOfWork()
    uow.users.users.append(user)

    async def main():
        async with uow:
            uow.commit_concurrent_write(lambda: user.link_github(99))

    asyncio.run(main())
    assert user.github_id == 99
