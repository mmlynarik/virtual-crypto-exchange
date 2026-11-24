from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

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
    EmailAvailability,
    EmailLoginCredentials,
    EmailRegisterCredentials,
    GithubCode,
    NewEmail,
    RefreshRequest,
    RegisterResponse,
    TokenPair,
    UserPublic,
)
from vce.dependencies import DBSession, HTTPClient
from vce.user.exceptions import UserAlreadyExists
from vce.user.repository import UsersRepository
from vce.utils import get_logger

LOGGER = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(creds: EmailRegisterCredentials, session: DBSession) -> RegisterResponse:
    try:
        return await services.register_with_password(
            creds, UsersRepository(session), RefreshTokenRepository(session), session
        )
    except UserAlreadyExists:
        raise HTTPException(status_code=409, detail=f"User with email {creds.email} already exists")


@router.get("/email-available")
async def email_available(email: Annotated[NewEmail, Query()], session: DBSession) -> EmailAvailability:
    """For the sign-up form. Takes the email the same way /register does, so both see the same address."""
    return EmailAvailability(available=await services.is_email_available(email, UsersRepository(session)))


@router.post("/login")
async def login(creds: EmailLoginCredentials, session: DBSession) -> TokenPair:
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
    except GithubAuthError as e:
        LOGGER.warning("GitHub login rejected: %s", e)
        raise UnauthorizedError("GitHub authentication failed")
    except UserAlreadyExists:
        LOGGER.info("GitHub login refused: the GitHub email already belongs to another account")
        raise HTTPException(status_code=409, detail="An account with this GitHub email already exists")


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
