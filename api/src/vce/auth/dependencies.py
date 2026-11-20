from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from vce.auth.exceptions import InvalidToken, UnauthorizedError
from vce.auth.services import get_user_from_access_token
from vce.dependencies import DBSession
from vce.user.domain import User
from vce.user.repository import UsersRepository

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    session: DBSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None:
        raise UnauthorizedError()
    try:
        return await get_user_from_access_token(credentials.credentials, UsersRepository(session))
    except InvalidToken:
        raise UnauthorizedError()


CurrentUser = Annotated[User, Depends(get_current_user)]
