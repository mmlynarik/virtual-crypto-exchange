from uuid import UUID

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from vce.auth.exceptions import (
    GithubAlreadyLinked,
    GithubEmailTaken,
    GithubLinkRequired,
    InvalidCredentials,
    InvalidToken,
    RefreshTokenReused,
)
from vce.auth.github import exchange_code_for_token, get_github_user
from vce.auth.repository import RefreshTokenRepository
from vce.auth.schemas import EmailLoginCredentials, EmailRegisterCredentials, RegisterResponse, TokenPair
from vce.auth.security import (
    create_access_token,
    create_github_pending_link_token,
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
from vce.user.services import (
    get_user_by_email,
    get_user_by_github_id,
    link_github,
    register_user_by_email,
    register_user_by_github,
    set_missing_email,
)
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
    user = check_password(await repo.get_by_email(creds.email), creds.password)
    LOGGER.info("User with id=%s logged in with password", user.id)
    return await start_session(user.id, token_repo, session)


def check_password(user: User | None, password: str) -> User:
    """
    The one place passwords are checked (password login and GitHub linking), so throttling added here
    later covers every endpoint that takes a password. Raises InvalidCredentials for a missing user, an
    account without a password, or a wrong password alike.
    """
    if user is None or user.password is None or user.salt is None:
        raise InvalidCredentials
    if not verify_password(password, user.password, user.salt):
        raise InvalidCredentials
    return user


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
        if await set_missing_email(user, github_user.email, repo=repo, session=session):
            LOGGER.info("User with id=%s got its email from GitHub", user_id)
    else:
        # Accounts are never merged by email: a password account is linked only once its password is confirmed
        email_owner = await get_user_by_email(github_user.email, repo=repo)
        if email_owner is not None:
            if email_owner.can_link_github:
                LOGGER.info(
                    "GitHub id=%s needs a password to link to user id=%s", github_user.id, email_owner.id
                )
                token = create_github_pending_link_token(email_owner.id, github_user.id)
                raise GithubLinkRequired(github_user.email, token)
            raise GithubEmailTaken
        user_create = UserCreateByGithub(github_id=github_user.id, email=github_user.email)
        try:
            user_id = (await register_user_by_github(user_create=user_create, repo=repo, session=session)).id
            LOGGER.info("User with id=%s registered via GitHub", user_id)
        except UserAlreadyExists:
            # Either the GitHub email was taken by a concurrent registration (re-raised for the router), or a
            # concurrent first login with the same GitHub account registered it a moment earlier
            existing = await get_user_by_github_id(github_user.id, repo=repo)
            if existing is None:
                raise
            user_id = existing.id

    LOGGER.info("User with id=%s logged in with GitHub", user_id)
    return await start_session(user_id, token_repo, session)


async def link_github_with_password(
    pending_link_token: str,
    password: str,
    repo: UsersRepository,
    token_repo: RefreshTokenRepository,
    session: AsyncSession,
) -> TokenPair:
    """
    Redeem the pending link token from a GitHub login (see login_with_github) with the account's password:
    the token proves the GitHub account, the password proves the existing account. Links the two and logs
    the user in.
    """
    payload = decode_token(pending_link_token, expected_type="github_pending_link")
    user = check_password(await repo.get_by_id(payload["userId"]), password)
    github_id: int = payload["githubId"]

    # The token is valid for minutes, so check again what the GitHub login saw
    if not user.can_link_github or await get_user_by_github_id(github_id, repo=repo):
        raise GithubAlreadyLinked
    await link_github(user, github_id, session)
    LOGGER.info("User with id=%s linked GitHub id=%s", user.id, github_id)
    return await start_session(user.id, token_repo, session)


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
