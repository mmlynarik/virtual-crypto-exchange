from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from vce.auth.exceptions import InvalidToken, UnauthorizedError
from vce.auth.services import get_user_from_access_token
from vce.dependencies import UnitOfWork
from vce.user.domain import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    uow: UnitOfWork,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    """The user is read in a unit of work of its own and returned detached: its columns stay readable,
    but it isn't tracked by the unit of work an endpoint opens."""
    if credentials is None:
        raise UnauthorizedError()
    try:
        return await get_user_from_access_token(credentials.credentials, uow)
    except InvalidToken:
        raise UnauthorizedError()


CurrentUser = Annotated[User, Depends(get_current_user)]
