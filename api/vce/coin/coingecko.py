from datetime import datetime

from httpx import AsyncClient

from vce.coin.domain import Coin
from vce.coin.exceptions import InvalidCoinSymbol
from vce.settings import VS_CURRENCY


async def get_coin_ids_from_symbol(client: AsyncClient, symbol: str) -> list[str]:
    url = "/coins/list"
    res = await client.get(url)
    ids = []
    for coin in res.json():
        if coin["symbol"] == symbol:
            ids.append(coin["id"])
    if not ids:
        raise InvalidCoinSymbol(f"Symbol {symbol} does not exist")
    return ids


async def get_coins_data(client: AsyncClient, ids: list[str], vs_currency: str = VS_CURRENCY) -> list[Coin]:
    ids_string = ", ".join(ids)
    url = "/coins/markets"
    res = await client.get(url, params={"ids": ids_string, "vs_currency": vs_currency})
    coins = []
    for coin in res.json():
        coins.append(
            Coin(
                id=coin["id"],
                name=coin["name"],
                symbol=coin["symbol"],
                current_price=coin["current_price"],
                market_cap=coin["market_cap"],
                circulating_supply=coin["circulating_supply"],
                total_supply=coin["total_supply"],
                max_supply=coin["max_supply"],
                last_updated=(
                    datetime.fromisoformat(coin["last_updated"]) if coin["last_updated"] is not None else None
                ),
            )
        )
    return coins
