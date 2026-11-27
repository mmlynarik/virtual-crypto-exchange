from httpx import AsyncClient

from vce.coin.coingecko import get_coin_ids_from_symbol, get_coins_data
from vce.coin.domain import Coin
from vce.coin.exceptions import CoinAlreadyExists, CoinNotFound
from vce.coin.schemas import CoinCreate, CoinUpdate
from vce.uow import AbstractUnitOfWork, UniqueViolation


async def add_coins(coin: CoinCreate, uow: AbstractUnitOfWork, client: AsyncClient) -> list[Coin]:
    """Store the coins CoinGecko has for the symbol. CoinGecko is asked first, outside the transaction."""
    ids = await get_coin_ids_from_symbol(client, coin.symbol)
    coins = await get_coins_data(client, ids)
    async with uow:
        if await uow.coins.exists(coin.symbol):
            raise CoinAlreadyExists(f"Symbol {coin.symbol} already exists in the database")
        for c in coins:
            await uow.coins.add(c)
        try:
            await uow.commit()
        except UniqueViolation as e:
            # A concurrent request stored the same coins between the check and the commit
            raise CoinAlreadyExists(f"Symbol {coin.symbol} already exists in the database") from e
    return coins


async def get_coins(symbol: str, uow: AbstractUnitOfWork) -> list[Coin]:
    async with uow:
        coins = await uow.coins.get_by_symbol(symbol)
    if not coins:
        raise CoinNotFound(f"Symbol {symbol} not found in database")
    return coins


async def delete_coin(id: str, uow: AbstractUnitOfWork) -> None:
    async with uow:
        if not await uow.coins.get_by_id(id):
            raise CoinNotFound(f"Coin with id {id} not found in database")
        await uow.coins.delete(id)
        await uow.commit()


async def update_coin(id: str, new_coin_values: CoinUpdate, uow: AbstractUnitOfWork) -> Coin:
    async with uow:
        current_coin = await uow.coins.get_by_id(id)
        if not current_coin:
            raise CoinNotFound(f"Coin with id {id} not found in database")
        for attr, value in new_coin_values.model_dump().items():
            setattr(current_coin, attr, value)
        await uow.commit()
    return current_coin


async def refresh_coins(uow: AbstractUnitOfWork, client: AsyncClient) -> None:
    """Update the market data of the stored coins from CoinGecko. Two short transactions, read and write,
    so that no database connection is held while CoinGecko answers."""
    async with uow:
        ids = [c.id for c in await uow.coins.list()]
    if not ids:
        return
    refreshed_coins = await get_coins_data(client, ids)
    async with uow:
        await uow.coins.update_market_data(refreshed_coins)
        await uow.commit()
