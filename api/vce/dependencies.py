from typing import Annotated

from fastapi import Depends, Request
from httpx import AsyncClient

from vce.db import SessionMaker
from vce.uow import AbstractUnitOfWork, SqlAlchemyUnitOfWork


def get_coin_client(request: Request) -> AsyncClient:
    return request.state.coingecko_client


def get_github_client(request: Request) -> AsyncClient:
    return request.state.github_client


def get_unit_of_work(sessionmaker: SessionMaker) -> AbstractUnitOfWork:
    return SqlAlchemyUnitOfWork(sessionmaker)


CoinClient = Annotated[AsyncClient, Depends(get_coin_client)]
GithubClient = Annotated[AsyncClient, Depends(get_github_client)]
UnitOfWork = Annotated[AbstractUnitOfWork, Depends(get_unit_of_work)]
