from fastapi import APIRouter, HTTPException

from vce.coin.exceptions import CoinAlreadyExists, CoinNotFound, InvalidCoinSymbol
from vce.coin.repository import CGCoinRepository
from vce.coin.schemas import CGCoinCreate, CGCoinResponse, CGCoinUpdate
from vce.coin.services import add_coins, delete_coin, get_coins, update_coin
from vce.dependencies import DBSession, HTTPClient

router = APIRouter(tags=["coins"])


@router.get("/coins/{symbol}")
async def get_coins_from_symbol(symbol: str, session: DBSession) -> list[CGCoinResponse]:
    repo = CGCoinRepository(session)
    try:
        coins = await get_coins(symbol, repo)
    except CoinNotFound:
        raise HTTPException(status_code=404, detail=f"Coins with symbol {symbol} not found in database")

    return [CGCoinResponse.model_validate(c) for c in coins]


@router.post("/coins", status_code=201)
async def add_coins_from_symbol(
    coin: CGCoinCreate, session: DBSession, client: HTTPClient
) -> list[CGCoinResponse]:
    repo = CGCoinRepository(session)
    try:
        coins = await add_coins(coin, repo, session, client)
    except InvalidCoinSymbol:
        raise HTTPException(status_code=422, detail=f"Coin symbol {coin.symbol} is not valid")
    except CoinAlreadyExists:
        raise HTTPException(
            status_code=422, detail=f"Coins with symbol {coin.symbol} already exist in database"
        )
    return [CGCoinResponse.model_validate(c) for c in coins]


@router.delete("/coins/{id}")
async def delete_coin_from_id(id: str, session: DBSession) -> dict:
    repo = CGCoinRepository(session)
    try:
        await delete_coin(id, repo, session)
    except CoinNotFound:
        raise HTTPException(status_code=404, detail=f"Coin with id {id} not found in database")
    return {"message": "OK"}


@router.put("/coins/{id}")
async def update_coin_from_id(id: str, new_coin_values: CGCoinUpdate, session: DBSession) -> CGCoinResponse:
    repo = CGCoinRepository(session)
    try:
        updated_coin = await update_coin(id, new_coin_values, repo, session)
    except CoinNotFound:
        raise HTTPException(status_code=404, detail=f"Coin with id {id} not found in database")
    return CGCoinResponse.model_validate(updated_coin)
