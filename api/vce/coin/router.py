from fastapi import APIRouter, HTTPException

from vce.coin.exceptions import CoinAlreadyExists, CoinNotFound, InvalidCoinSymbol
from vce.coin.schemas import CoinCreate, CoinResponse, CoinUpdate
from vce.coin.services import add_coins, delete_coin, get_coins, update_coin
from vce.dependencies import CoinClient, UnitOfWork

router = APIRouter(tags=["coins"])


@router.get("/coins/{symbol}")
async def get_coins_from_symbol(symbol: str, uow: UnitOfWork) -> list[CoinResponse]:
    try:
        coins = await get_coins(symbol, uow)
    except CoinNotFound:
        raise HTTPException(status_code=404, detail=f"Coins with symbol {symbol} not found in database")

    return [CoinResponse.model_validate(c) for c in coins]


@router.post("/coins", status_code=201)
async def add_coins_from_symbol(coin: CoinCreate, uow: UnitOfWork, client: CoinClient) -> list[CoinResponse]:
    try:
        coins = await add_coins(coin, uow, client)
    except InvalidCoinSymbol:
        raise HTTPException(status_code=422, detail=f"Coin symbol {coin.symbol} is not valid")
    except CoinAlreadyExists:
        raise HTTPException(
            status_code=422, detail=f"Coins with symbol {coin.symbol} already exist in database"
        )
    return [CoinResponse.model_validate(c) for c in coins]


@router.delete("/coins/{id}")
async def delete_coin_from_id(id: str, uow: UnitOfWork) -> dict:
    try:
        await delete_coin(id, uow)
    except CoinNotFound:
        raise HTTPException(status_code=404, detail=f"Coin with id {id} not found in database")
    return {"message": "OK"}


@router.put("/coins/{id}")
async def update_coin_from_id(id: str, new_coin_values: CoinUpdate, uow: UnitOfWork) -> CoinResponse:
    try:
        updated_coin = await update_coin(id, new_coin_values, uow)
    except CoinNotFound:
        raise HTTPException(status_code=404, detail=f"Coin with id {id} not found in database")
    return CoinResponse.model_validate(updated_coin)
