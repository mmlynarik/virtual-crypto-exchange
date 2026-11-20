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
    await session.refresh(user)
    return UserCreated(id=user.id)  # type: ignore


async def register_user_by_email(
    user_create: UserCreateByEmail, repo: UsersRepository, session: AsyncSession
) -> UserCreated:
    existing_user = await get_user_by_email(user_create.email, repo=repo)
    if existing_user:
        raise UserAlreadyExists
    user = User(
        id=None,
        email=user_create.email,
        password=user_create.password,
        salt=user_create.salt,
        github_id=None,
        github_name=None,
    )
    return await _save_new_user(user, repo, session)


async def register_user_by_github(
    user_create: UserCreateByGithub, repo: UsersRepository, session: AsyncSession
) -> UserCreated:
    existing_user = await get_user_by_github_id(user_create.github_id, repo=repo)
    if existing_user:
        raise UserAlreadyExists
    user = User(
        id=None,
        email=None,
        password=None,
        salt=None,
        github_id=user_create.github_id,
        github_name=user_create.github_name,
    )
    return await _save_new_user(user, repo, session)
