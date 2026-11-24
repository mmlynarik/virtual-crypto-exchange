from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vce.user.domain import User
from vce.utils import get_logger

LOGGER = get_logger(__name__)


class UsersRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, user: User):
        self.session.add(user)
        LOGGER.info("New user added to database: %s", user)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)  # type: ignore
        result = await self.session.execute(stmt)
        return result.scalars().one_or_none()

    async def get_by_github_id(self, github_id: int) -> User | None:
        stmt = select(User).where(User.github_id == github_id)  # type: ignore
        result = await self.session.execute(stmt)
        return result.scalars().one_or_none()

    async def get_by_id(self, id: UUID) -> User | None:
        return await self.session.get(User, id)
