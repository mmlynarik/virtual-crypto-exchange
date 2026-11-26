from typing import Annotated

from fastapi import Depends, Request
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from vce.db import SessionMaker, get_db_session
from vce.uow import AbstractUnitOfWork, SqlAlchemyUnitOfWork


def get_http_client(request: Request) -> AsyncClient:
    return request.state.http_client


def get_unit_of_work(sessionmaker: SessionMaker) -> AbstractUnitOfWork:
    return SqlAlchemyUnitOfWork(sessionmaker)


HTTPClient = Annotated[AsyncClient, Depends(get_http_client)]
DBSession = Annotated[AsyncSession, Depends(get_db_session)]
UnitOfWork = Annotated[AbstractUnitOfWork, Depends(get_unit_of_work)]
