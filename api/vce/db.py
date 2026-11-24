from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Every domain's tables (vce/<domain>/orm.py) are defined on this MetaData.
# It's what Alembic compares against the database; the schema itself is created by migrations.
metadata = MetaData()


def get_sessionmaker(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.state.sessionmaker


SessionMaker = Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)]


async def get_db_session(sessionmaker: SessionMaker) -> AsyncIterator[AsyncSession]:
    async with sessionmaker() as session:
        yield session
