from uuid import UUID

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from vce.auth.exceptions import InvalidCredentials, InvalidToken, RefreshTokenReused
from vce.auth.github import exchange_code_for_token, get_github_user
from vce.auth.repository import RefreshTokenRepository
from vce.auth.schemas import EmailLoginCredentials, EmailRegisterCredentials, RegisterResponse, TokenPair
from vce.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_salt,
    hash_password,
    verify_password,
)
from vce.user.domain import User
from vce.user.exceptions import UserAlreadyExists
from vce.user.repository import UsersRepository
from vce.user.schemas import UserCreateByEmail, UserCreateByGithub
from vce.user.services import get_user_by_github_id, register_user_by_email, register_user_by_github
from vce.utils import get_logger

LOGGER = get_logger(__name__)


async def issue_token_pair(
    user_id: UUID, token_repo: RefreshTokenRepository, session: AsyncSession, family_id: UUID | None = None
) -> TokenPair:
    """Issue a token pair; without family_id a new refresh token family (session) is started."""
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id, family_id)
    await token_repo.add(refresh_token)
    await session.commit()
    return TokenPair(access_token=access_token, refresh_token=refresh_token.token)


async def start_session(
    user_id: UUID, token_repo: RefreshTokenRepository, session: AsyncSession
) -> TokenPair:
    """Start a new refresh token family (one per login) and issue the first token pair."""
    return await issue_token_pair(user_id, token_repo, session)


async def register_with_password(
    creds: EmailRegisterCredentials,
    user_repo: UsersRepository,
    token_repo: RefreshTokenRepository,
    session: AsyncSession,
) -> RegisterResponse:
    salt = generate_salt()
    user_create = UserCreateByEmail(
        email=creds.email, password=hash_password(creds.password, salt), salt=salt
    )
    created = await register_user_by_email(user_create=user_create, repo=user_repo, session=session)
    tokens = await start_session(created.id, token_repo, session)
    LOGGER.info("User with id=%s registered", created.id)
    return RegisterResponse(user_id=created.id, **tokens.model_dump())


async def is_email_available(email: str, repo: UsersRepository) -> bool:
    return await repo.get_by_email(email) is None


async def login_with_password(
    creds: EmailLoginCredentials,
    repo: UsersRepository,
    token_repo: RefreshTokenRepository,
    session: AsyncSession,
) -> TokenPair:
    user = await repo.get_by_email(creds.email)
    if not user or user.password is None or user.salt is None:
        raise InvalidCredentials
    if not verify_password(creds.password, user.password, user.salt):
        raise InvalidCredentials
    LOGGER.info("User with id=%s logged in with password", user.id)
    return await start_session(user.id, token_repo, session)


async def login_with_github(
    code: str,
    repo: UsersRepository,
    token_repo: RefreshTokenRepository,
    session: AsyncSession,
    client: AsyncClient,
) -> TokenPair:
    github_access_token = await exchange_code_for_token(client, code)
    github_user = await get_github_user(client, github_access_token)

    user = await get_user_by_github_id(github_user.id, repo=repo)
    if user:
        user_id = user.id
    else:
        user_create = UserCreateByGithub(github_id=github_user.id, github_name=github_user.name)
        try:
            user_id = (await register_user_by_github(user_create=user_create, repo=repo, session=session)).id
            LOGGER.info("User with id=%s registered via GitHub", user_id)
        except UserAlreadyExists:
            # A concurrent first login with the same GitHub account registered it a moment earlier
            existing = await get_user_by_github_id(github_user.id, repo=repo)
            if existing is None:
                raise
            user_id = existing.id

    LOGGER.info("User with id=%s logged in with GitHub", user_id)
    return await start_session(user_id, token_repo, session)


async def rotate_refresh_token(
    refresh_token: str, repo: UsersRepository, token_repo: RefreshTokenRepository, session: AsyncSession
) -> TokenPair:
    payload = decode_token(refresh_token, expected_type="refresh")

    record = await token_repo.consume(payload["jti"])
    if record is None:
        # Signature is valid but token is no longer whitelisted: it was already rotated or revoked.
        # Treat as theft and kill the whole session (family).
        await token_repo.revoke_family(payload["fam"])
        await session.commit()
        LOGGER.warning(
            "Refresh token reuse detected for user id=%s, family %s revoked",
            payload["userId"],
            payload["fam"],
        )
        raise RefreshTokenReused

    user = await repo.get_by_id(record.user_id)
    if not user:
        await session.commit()
        raise InvalidToken("User in refresh token does not exist")

    await token_repo.delete_expired_for_user(record.user_id)
    return await issue_token_pair(record.user_id, token_repo, session, family_id=record.family_id)


async def logout(refresh_token: str, token_repo: RefreshTokenRepository, session: AsyncSession) -> None:
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except InvalidToken:
        return
    await token_repo.revoke_family(payload["fam"])
    await session.commit()


async def get_user_from_access_token(token: str, repo: UsersRepository) -> User:
    payload = decode_token(token, expected_type="access")
    user = await repo.get_by_id(payload["userId"])
    if not user:
        raise InvalidToken("User in access token does not exist")
    return user
