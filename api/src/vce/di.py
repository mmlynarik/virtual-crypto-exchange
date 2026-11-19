from fastapi import Request
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from vce.settings import BACKEND_DB_URL

engine = create_async_engine(BACKEND_DB_URL)

Session = async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session():
    async with Session() as session:
        yield session


async def get_http_client(request: Request) -> AsyncClient:
    return request.app.state.http_client
