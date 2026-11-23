import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from vce.user.domain import User
from vce.user.exceptions import UserAlreadyExists
from vce.user.repository import UsersRepository
from vce.user.schemas import UserCreateByEmail, UserCreateByGithub, UserCreated


async def get_user_by_email(email: str, repo: UsersRepository) -> User | None:
    return await repo.get_by_email(email=email)


async def get_user_by_github_id(github_id: int, repo: UsersRepository) -> User | None:
    return await repo.get_by_github_id(github_id=github_id)


async def _save_new_user(user: User, repo: UsersRepository, session: AsyncSession) -> UserCreated:
    """Insert the user. A concurrent registration can pass the caller's existence check at the same time;
    the unique constraints on email and github_id then reject the second insert."""
    await repo.add(user=user)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise UserAlreadyExists from e
    return UserCreated(id=user.id)


async def register_user_by_email(
    user_create: UserCreateByEmail, repo: UsersRepository, session: AsyncSession
) -> UserCreated:
    existing_user = await get_user_by_email(user_create.email, repo=repo)
    if existing_user:
        raise UserAlreadyExists
    user = User(
        id=uuid.uuid7(),
        email=user_create.email,
        password=user_create.password,
        salt=user_create.salt,
        github_id=None,
    )
    return await _save_new_user(user, repo, session)


async def register_user_by_github(
    user_create: UserCreateByGithub, repo: UsersRepository, session: AsyncSession
) -> UserCreated:
    """Raises UserAlreadyExists when the GitHub account is registered, or when its email already belongs
    to another account (e.g. one registered with a password). Accounts are never merged by email."""
    if await get_user_by_github_id(user_create.github_id, repo=repo):
        raise UserAlreadyExists
    if await get_user_by_email(user_create.email, repo=repo):
        raise UserAlreadyExists
    user = User(
        id=uuid.uuid7(),
        email=user_create.email,
        password=None,
        salt=None,
        github_id=user_create.github_id,
    )
    return await _save_new_user(user, repo, session)


async def set_missing_email(user: User, email: str, repo: UsersRepository, session: AsyncSession) -> bool:
    """Give a user without an email (GitHub users registered before emails were fetched) this one.
    Skipped, returning False, when another account already has the email."""
    if user.email is not None:
        return False
    if await get_user_by_email(email, repo=repo):
        return False
    user.email = email
    try:
        await session.commit()
    except IntegrityError:
        # Another account took the email between the check and the commit
        await session.rollback()
        return False
    return True
