from typing import Annotated

from fastapi import Depends, Request
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from vce.db import get_db_session


def get_http_client(request: Request) -> AsyncClient:
    return request.state.http_client


HTTPClient = Annotated[AsyncClient, Depends(get_http_client)]
DBSession = Annotated[AsyncSession, Depends(get_db_session)]
