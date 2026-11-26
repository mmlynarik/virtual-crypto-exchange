from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from vce.auth import services
from vce.auth.dependencies import CurrentUser
from vce.auth.exceptions import (
    GithubAlreadyLinked,
    GithubAuthError,
    GithubEmailTaken,
    GithubLinkRequired,
    InvalidCredentials,
    InvalidToken,
    RefreshTokenReused,
    UnauthorizedError,
)
from vce.auth.schemas import (
    EmailAvailability,
    EmailLoginCredentials,
    EmailRegisterCredentials,
    GithubCode,
    GithubConflict,
    GithubConflictResponse,
    GithubPendingLinkRequest,
    NewEmail,
    RefreshRequest,
    RegisterResponse,
    TokenPair,
    UserPublic,
)
from vce.dependencies import HTTPClient, UnitOfWork
from vce.user.exceptions import UserAlreadyExists
from vce.utils import get_logger

LOGGER = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(creds: EmailRegisterCredentials, uow: UnitOfWork) -> RegisterResponse:
    try:
        return await services.register_with_password(creds, uow)
    except UserAlreadyExists:
        raise HTTPException(status_code=409, detail=f"User with email {creds.email} already exists")


@router.get("/email-available")
async def email_available(email: Annotated[NewEmail, Query()], uow: UnitOfWork) -> EmailAvailability:
    """For the sign-up form. Takes the email the same way /register does, so both see the same address."""
    return EmailAvailability(available=await services.is_email_available(email, uow))


@router.post("/login")
async def login(creds: EmailLoginCredentials, uow: UnitOfWork) -> TokenPair:
    try:
        return await services.login_with_password(creds, uow)
    except InvalidCredentials:
        raise UnauthorizedError("Incorrect email or password")


def github_conflict(conflict: GithubConflict) -> HTTPException:
    return HTTPException(status_code=409, detail=conflict.model_dump(exclude_none=True))


@router.post("/github", responses={409: {"model": GithubConflictResponse}})
async def login_github(body: GithubCode, uow: UnitOfWork, client: HTTPClient) -> TokenPair:
    try:
        return await services.login_with_github(body.code, uow, client)
    except GithubAuthError as e:
        LOGGER.warning("GitHub login rejected: %s", e)
        raise UnauthorizedError("GitHub authentication failed")
    except GithubLinkRequired as e:
        raise github_conflict(
            GithubConflict(
                code="ACCOUNT_EXISTS",
                message="An account with this email already exists. Enter its password to connect GitHub.",
                email=e.email,
                pending_link_token=e.pending_link_token,
            )
        )
    except GithubEmailTaken, UserAlreadyExists:
        LOGGER.info("GitHub login refused: the GitHub email belongs to an account that can't be linked")
        raise github_conflict(
            GithubConflict(code="EMAIL_TAKEN", message="An account with this GitHub email already exists.")
        )


@router.post("/github/link-pending")
async def link_github_pending(body: GithubPendingLinkRequest, uow: UnitOfWork) -> TokenPair:
    """Link GitHub to the account that /auth/github answered ACCOUNT_EXISTS for, once its password is
    confirmed, and log in."""
    try:
        return await services.link_github_with_password(body.pending_link_token, body.password, uow)
    except InvalidToken:
        raise UnauthorizedError("Invalid or expired link token")
    except InvalidCredentials:
        raise UnauthorizedError("Incorrect email or password")
    except GithubAlreadyLinked:
        raise HTTPException(status_code=409, detail="This account or this GitHub account is already linked")


@router.post("/refresh")
async def refresh(body: RefreshRequest, uow: UnitOfWork) -> TokenPair:
    try:
        return await services.rotate_refresh_token(body.refresh_token, uow)
    except RefreshTokenReused:
        raise UnauthorizedError("Refresh token has already been used; session revoked")
    except InvalidToken:
        raise UnauthorizedError("Invalid refresh token")


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshRequest, uow: UnitOfWork) -> Response:
    await services.logout(body.refresh_token, uow)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
async def me(user: CurrentUser) -> UserPublic:
    return UserPublic.model_validate(user)
