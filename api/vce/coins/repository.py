from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vce.coins.domain import Coin
from vce.utils import get_logger

LOGGER = get_logger(__name__)


class CoinRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, coin: Coin):
        self.session.add(coin)
        LOGGER.info("New coin added to database: %s", coin)

    async def exists(self, symbol: str) -> bool:
        stmt = select(Coin).where(Coin.symbol == symbol)  # type: ignore
        result = await self.session.execute(stmt)
        return bool(result.scalars().all())

    async def get_by_symbol(self, symbol: str) -> list[Coin]:
        stmt = select(Coin).where(Coin.symbol == symbol)  # type: ignore
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, id: str) -> Coin | None:
        return await self.session.get(Coin, id)

    async def list(self) -> list[Coin]:
        stmt = select(Coin)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, id: str):
        obj = await self.session.get(Coin, id)
        await self.session.delete(obj)

    # Sequence, not list: inside this class, list is the method above
    async def update_market_data(self, coins: Sequence[Coin]):
        """Bulk UPDATE by id of the stored coins' market data from these; name and symbol stay."""
        if not coins:
            return
        await self.session.execute(
            update(Coin),
            [
                {
                    "id": c.id,
                    "current_price": c.current_price,
                    "market_cap": c.market_cap,
                    "circulating_supply": c.circulating_supply,
                    "total_supply": c.total_supply,
                    "max_supply": c.max_supply,
                    "last_updated": c.last_updated,
                }
                for c in coins
            ],
        )
