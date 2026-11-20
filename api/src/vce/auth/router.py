from fastapi import APIRouter, HTTPException, Response, status

from vce.auth import services
from vce.auth.dependencies import CurrentUser
from vce.auth.exceptions import (
    GithubAuthError,
    InvalidCredentials,
    InvalidToken,
    RefreshTokenReused,
    UnauthorizedError,
)
from vce.auth.repository import RefreshTokenRepository
from vce.auth.schemas import (
    EmailCredentials,
    GithubCode,
    LoginCredentials,
    RefreshRequest,
    RegisterResponse,
    TokenPair,
    UserPublic,
)
from vce.dependencies import DBSession, HTTPClient
from vce.user.exceptions import UserAlreadyExists
from vce.user.repository import UsersRepository

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(creds: EmailCredentials, session: DBSession) -> RegisterResponse:
    try:
        return await services.register_with_password(
            creds, UsersRepository(session), RefreshTokenRepository(session), session
        )
    except UserAlreadyExists:
        raise HTTPException(status_code=409, detail=f"User with email {creds.email} already exists")


@router.post("/login")
async def login(creds: LoginCredentials, session: DBSession) -> TokenPair:
    try:
        return await services.login_with_password(
            creds, UsersRepository(session), RefreshTokenRepository(session), session
        )
    except InvalidCredentials:
        raise UnauthorizedError("Incorrect email or password")


@router.post("/github")
async def login_github(body: GithubCode, session: DBSession, client: HTTPClient) -> TokenPair:
    try:
        return await services.login_with_github(
            body.code, UsersRepository(session), RefreshTokenRepository(session), session, client
        )
    except GithubAuthError:
        raise UnauthorizedError("GitHub authentication failed")


@router.post("/refresh")
async def refresh(body: RefreshRequest, session: DBSession) -> TokenPair:
    try:
        return await services.rotate_refresh_token(
            body.refresh_token, UsersRepository(session), RefreshTokenRepository(session), session
        )
    except RefreshTokenReused:
        raise UnauthorizedError("Refresh token has already been used; session revoked")
    except InvalidToken:
        raise UnauthorizedError("Invalid refresh token")


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshRequest, session: DBSession) -> Response:
    await services.logout(body.refresh_token, RefreshTokenRepository(session), session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
async def me(user: CurrentUser) -> UserPublic:
    return UserPublic.model_validate(user)
