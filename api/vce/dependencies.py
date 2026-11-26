from typing import Annotated

from fastapi import Depends, Request
from httpx import AsyncClient

from vce.db import SessionMaker
from vce.uow import AbstractUnitOfWork, SqlAlchemyUnitOfWork


def get_http_client(request: Request) -> AsyncClient:
    return request.state.http_client


def get_unit_of_work(sessionmaker: SessionMaker) -> AbstractUnitOfWork:
    return SqlAlchemyUnitOfWork(sessionmaker)


HTTPClient = Annotated[AsyncClient, Depends(get_http_client)]
UnitOfWork = Annotated[AbstractUnitOfWork, Depends(get_unit_of_work)]
