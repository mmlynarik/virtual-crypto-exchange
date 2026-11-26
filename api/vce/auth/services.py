from uuid import UUID

from httpx import AsyncClient

from vce.auth.domain import authenticate
from vce.auth.exceptions import (
    GithubAlreadyLinked,
    GithubEmailTaken,
    GithubLinkRequired,
    InvalidToken,
    RefreshTokenReused,
)
from vce.auth.github import GithubUser, exchange_code_for_token, get_github_user
from vce.auth.schemas import EmailLoginCredentials, EmailRegisterCredentials, RegisterResponse, TokenPair
from vce.auth.security import (
    create_access_token,
    create_github_pending_link_token,
    create_refresh_token,
    decode_token,
)
from vce.uow import AbstractUnitOfWork, UniqueViolation
from vce.user.domain import User
from vce.user.exceptions import CannotLinkGithub, UserAlreadyExists
from vce.utils import get_logger

LOGGER = get_logger(__name__)


async def issue_token_pair(
    user_id: UUID, uow: AbstractUnitOfWork, family_id: UUID | None = None
) -> TokenPair:
    """Issue a token pair; without family_id a new refresh token family (session) is started. The refresh
    token is valid once the caller commits."""
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id, family_id)
    await uow.refresh_tokens.add(refresh_token)
    return TokenPair(access_token=access_token, refresh_token=refresh_token.token)


async def start_session(user_id: UUID, uow: AbstractUnitOfWork) -> TokenPair:
    """Start a new refresh token family (one per login) and issue the first token pair."""
    return await issue_token_pair(user_id, uow)


async def register_with_password(
    creds: EmailRegisterCredentials, uow: AbstractUnitOfWork
) -> RegisterResponse:
    async with uow:
        if await uow.users.get_by_email(creds.email):
            raise UserAlreadyExists
        user = User.from_password(email=creds.email, password=creds.password)
        await uow.users.add(user)
        tokens = await start_session(user.id, uow)
        try:
            await uow.commit()
        except UniqueViolation as e:
            raise UserAlreadyExists from e
    LOGGER.info("User with id=%s registered", user.id)
    return RegisterResponse(user_id=user.id, **tokens.model_dump())


async def is_email_available(email: str, uow: AbstractUnitOfWork) -> bool:
    async with uow:
        return await uow.users.get_by_email(email) is None


async def login_with_password(creds: EmailLoginCredentials, uow: AbstractUnitOfWork) -> TokenPair:
    async with uow:
        user = authenticate(await uow.users.get_by_email(creds.email), creds.password)
        tokens = await start_session(user.id, uow)
        await uow.commit()
    LOGGER.info("User with id=%s logged in with password", user.id)
    return tokens


async def login_with_github(code: str, uow: AbstractUnitOfWork, client: AsyncClient) -> TokenPair:
    github_access_token = await exchange_code_for_token(client, code)
    github_user = await get_github_user(client, github_access_token)

    async with uow:
        user = await uow.users.get_by_github_id(github_user.id)
        if user:
            user_id = user.id
        else:
            await check_github_email_is_free(github_user, uow)
            user_id = await register_github_user(github_user, uow)
        tokens = await start_session(user_id, uow)
        await uow.commit()
    LOGGER.info("User with id=%s logged in with GitHub", user_id)
    return tokens


async def check_github_email_is_free(github_user: GithubUser, uow: AbstractUnitOfWork) -> None:
    """
    Accounts are never merged by email. Raises GithubLinkRequired, with a pending link token, when the
    GitHub email belongs to a password account: its password links the two (see link_github_with_password).
    Raises GithubEmailTaken when it belongs to an account that can't be linked.
    """
    email_owner = await uow.users.get_by_email(github_user.email)
    if email_owner is None:
        return
    if email_owner.can_link_github:
        LOGGER.info("GitHub id=%s needs a password to link to user id=%s", github_user.id, email_owner.id)
        token = create_github_pending_link_token(email_owner.id, github_user.id)
        raise GithubLinkRequired(github_user.email, token)
    raise GithubEmailTaken


async def register_github_user(github_user: GithubUser, uow: AbstractUnitOfWork) -> UUID:
    """
    Register the GitHub account as a new user and return its id. Committed on its own, ahead of the login,
    so that a concurrent request taking the GitHub account or the email fails only this step: when a
    concurrent first login with the same GitHub account registered it a moment earlier, that user's id is
    returned; when a concurrent registration took the email, UserAlreadyExists is raised for the router.
    """
    user = User.from_github(github_id=github_user.id, email=github_user.email)
    await uow.users.add(user)
    try:
        await uow.commit()
    except UniqueViolation as e:
        existing = await uow.users.get_by_github_id(github_user.id)
        if existing is None:
            raise UserAlreadyExists from e
        return existing.id
    LOGGER.info("User with id=%s registered via GitHub", user.id)
    return user.id


async def link_github_with_password(
    pending_link_token: str, password: str, uow: AbstractUnitOfWork
) -> TokenPair:
    """
    Redeem the pending link token from a GitHub login (see login_with_github) with the account's password:
    the token proves the GitHub account, the password proves the existing account. Links the two and logs
    the user in, in one transaction.
    """
    payload = decode_token(pending_link_token, expected_type="github_pending_link")
    github_id: int = payload["githubId"]

    async with uow:
        user = authenticate(await uow.users.get_by_id(payload["userId"]), password)
        await uow.users.lock(user)
        # The token is valid for minutes, so check again what the GitHub login saw
        if await uow.users.get_by_github_id(github_id):
            raise GithubAlreadyLinked
        try:
            user.link_github(github_id)
        except CannotLinkGithub as e:
            raise GithubAlreadyLinked from e
        tokens = await start_session(user.id, uow)
        try:
            await uow.commit()
        except UniqueViolation as e:
            raise GithubAlreadyLinked from e
    LOGGER.info("User with id=%s linked GitHub id=%s", user.id, github_id)
    return tokens


async def rotate_refresh_token(refresh_token: str, uow: AbstractUnitOfWork) -> TokenPair:
    payload = decode_token(refresh_token, expected_type="refresh")

    async with uow:
        record = await uow.refresh_tokens.consume(payload["jti"])
        if record is None:
            await uow.refresh_tokens.revoke_family(payload["fam"])
            await uow.commit()
            LOGGER.warning(
                "Refresh token reuse detected for user id=%s, family %s revoked",
                payload["userId"],
                payload["fam"],
            )
            raise RefreshTokenReused

        user = await uow.users.get_by_id(record.user_id)
        if not user:
            await uow.commit()
            raise InvalidToken("User in refresh token does not exist")

        await uow.refresh_tokens.delete_expired_for_user(record.user_id)
        tokens = await issue_token_pair(record.user_id, uow, family_id=record.family_id)
        await uow.commit()
    return tokens


async def logout(refresh_token: str, uow: AbstractUnitOfWork) -> None:
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except InvalidToken:
        return
    async with uow:
        await uow.refresh_tokens.revoke_family(payload["fam"])
        await uow.commit()


async def get_user_from_access_token(token: str, uow: AbstractUnitOfWork) -> User:
    payload = decode_token(token, expected_type="access")
    async with uow:
        user = await uow.users.get_by_id(payload["userId"])
    if not user:
        raise InvalidToken("User in access token does not exist")
    return user
