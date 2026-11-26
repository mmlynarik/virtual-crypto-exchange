"""The coin services, with CoinGecko faked over HTTP."""

import asyncio
from datetime import datetime

import httpx
import pytest

from tests.fakes import FakeUnitOfWork
from vce.coin import services
from vce.coin.domain import CGCoin
from vce.coin.exceptions import CoinAlreadyExists, CoinNotFound, InvalidCoinSymbol
from vce.coin.schemas import CGCoinCreate, CGCoinUpdate

MARKETS = {
    "bitcoin": {
        "id": "bitcoin",
        "name": "Bitcoin",
        "symbol": "btc",
        "current_price": 100.0,
        "market_cap": 1000.0,
        "circulating_supply": 10.0,
        "total_supply": 21.0,
        "max_supply": 21.0,
        "last_updated": "2026-11-26T10:00:00.000Z",
    },
    "ethereum": {
        "id": "ethereum",
        "name": "Ethereum",
        "symbol": "eth",
        "current_price": 50.0,
        "market_cap": 500.0,
        "circulating_supply": 10.0,
        "total_supply": None,
        "max_supply": None,
        "last_updated": "2026-11-26T10:00:00.000Z",
    },
}


def coingecko(requests: list[str] | None = None) -> httpx.AsyncClient:
    """CoinGecko's /coins/list and /coins/markets for MARKETS. Records the requested paths in requests."""

    def handler(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(request.url.path)
        if request.url.path == "/coins/list":
            return httpx.Response(
                200, json=[{"id": m["id"], "symbol": m["symbol"]} for m in MARKETS.values()]
            )
        if request.url.path == "/coins/markets":
            ids = [i.strip() for i in request.url.params["ids"].split(",")]
            return httpx.Response(200, json=[MARKETS[i] for i in ids if i in MARKETS])
        return httpx.Response(404)

    return httpx.AsyncClient(base_url="https://coingecko.test", transport=httpx.MockTransport(handler))


def stored_coin(id: str = "bitcoin", symbol: str = "btc", current_price: float | None = 1.0) -> CGCoin:
    return CGCoin(
        id=id,
        name=id.title(),
        symbol=symbol,
        current_price=current_price,
        market_cap=None,
        circulating_supply=None,
        total_supply=None,
        max_supply=None,
        last_updated=None,
    )


def uow_with(*coins: CGCoin, failing_commits: int = 0) -> FakeUnitOfWork:
    uow = FakeUnitOfWork(failing_commits=failing_commits)
    for coin in coins:
        uow.coins.coins[coin.id] = coin
    return uow


def test_add_coins_stores_the_coins_of_the_symbol():
    uow = uow_with()
    coins = asyncio.run(services.add_coins(CGCoinCreate(symbol="btc"), uow, coingecko()))
    assert [c.id for c in coins] == ["bitcoin"]
    assert list(uow.coins.coins) == ["bitcoin"]
    assert uow.coins.coins["bitcoin"].current_price == 100.0
    assert uow.coins.coins["bitcoin"].last_updated == datetime.fromisoformat("2026-11-26T10:00:00+00:00")
    assert uow.commits == 1


def test_add_coins_of_stored_symbol_rejected():
    uow = uow_with(stored_coin())
    with pytest.raises(CoinAlreadyExists):
        asyncio.run(services.add_coins(CGCoinCreate(symbol="btc"), uow, coingecko()))
    assert uow.commits == 0


def test_add_coins_stored_meanwhile_rejected():
    # A concurrent request stored the same coins between the check and the commit
    uow = uow_with(failing_commits=1)
    with pytest.raises(CoinAlreadyExists):
        asyncio.run(services.add_coins(CGCoinCreate(symbol="btc"), uow, coingecko()))
    assert uow.commits == 0


def test_add_coins_of_unknown_symbol_rejected():
    uow = uow_with()
    with pytest.raises(InvalidCoinSymbol):
        asyncio.run(services.add_coins(CGCoinCreate(symbol="nope"), uow, coingecko()))
    assert uow.coins.coins == {}


def test_get_coins():
    bitcoin = stored_coin()
    uow = uow_with(bitcoin, stored_coin("ethereum", "eth"))
    assert asyncio.run(services.get_coins("btc", uow)) == [bitcoin]
    assert uow.commits == 0


def test_get_coins_of_unknown_symbol_rejected():
    with pytest.raises(CoinNotFound):
        asyncio.run(services.get_coins("btc", uow_with()))


def test_delete_coin():
    uow = uow_with(stored_coin())
    asyncio.run(services.delete_coin("bitcoin", uow))
    assert uow.coins.coins == {}
    assert uow.commits == 1


def test_delete_missing_coin_rejected():
    uow = uow_with()
    with pytest.raises(CoinNotFound):
        asyncio.run(services.delete_coin("bitcoin", uow))
    assert uow.commits == 0


def test_update_coin():
    bitcoin = stored_coin()
    uow = uow_with(bitcoin)
    values = CGCoinUpdate(
        name="Bitcoin",
        symbol="btc",
        current_price=2.0,
        market_cap=20.0,
        circulating_supply=10.0,
        total_supply=21.0,
        max_supply=21.0,
        last_updated=datetime.fromisoformat("2026-11-26T10:00:00+00:00"),
    )
    assert asyncio.run(services.update_coin("bitcoin", values, uow)) is bitcoin
    assert (bitcoin.current_price, bitcoin.market_cap) == (2.0, 20.0)
    assert uow.commits == 1


def test_update_missing_coin_rejected():
    values = CGCoinUpdate(
        name="Bitcoin",
        symbol="btc",
        current_price=2.0,
        market_cap=20.0,
        circulating_supply=10.0,
        total_supply=21.0,
        max_supply=21.0,
        last_updated=datetime.fromisoformat("2026-11-26T10:00:00+00:00"),
    )
    uow = uow_with()
    with pytest.raises(CoinNotFound):
        asyncio.run(services.update_coin("bitcoin", values, uow))
    assert uow.commits == 0


def test_refresh_coins_updates_the_market_data_of_stored_coins():
    bitcoin = stored_coin(current_price=1.0)
    uow = uow_with(bitcoin)
    asyncio.run(services.refresh_coins(uow, coingecko()))
    assert (bitcoin.name, bitcoin.current_price, bitcoin.market_cap) == ("Bitcoin", 100.0, 1000.0)
    assert uow.commits == 1


def test_refresh_coins_without_stored_coins_does_nothing():
    requests: list[str] = []
    uow = uow_with()
    asyncio.run(services.refresh_coins(uow, coingecko(requests)))
    assert requests == []
    assert uow.commits == 0
