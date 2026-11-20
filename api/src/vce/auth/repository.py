from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from vce.auth.domain import RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, token: RefreshToken):
        self.session.add(token)

    async def consume(self, jti: str) -> RefreshToken | None:
        """Atomically remove a whitelisted token. Returns None if it was already used or revoked."""
        stmt = (
            delete(RefreshToken)
            .where(RefreshToken.jti == jti)  # type: ignore[misc, arg-type]
            .returning(RefreshToken)
        )
        result = await self.session.execute(stmt)
        return result.scalars().one_or_none()

    async def revoke_family(self, family_id: str):
        stmt = delete(RefreshToken).where(RefreshToken.family_id == family_id)  # type: ignore[misc, arg-type]
        await self.session.execute(stmt)

    async def delete_expired_for_user(self, user_id: int):
        stmt = delete(RefreshToken).where(
            RefreshToken.user_id == user_id,  # type: ignore[misc, arg-type]
            RefreshToken.expires_at < datetime.now(UTC),  # type: ignore[misc, arg-type]
        )
        await self.session.execute(stmt)
