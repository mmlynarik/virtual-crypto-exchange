from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CoinCreate(BaseModel):
    symbol: str


class CoinUpdate(BaseModel):
    name: str
    symbol: str
    current_price: float
    market_cap: float
    circulating_supply: float
    total_supply: float
    max_supply: float
    last_updated: datetime


class CoinResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    symbol: str
    current_price: float | None
    market_cap: float | None
    circulating_supply: float | None
    total_supply: float | None
    max_supply: float | None
    last_updated: datetime | None
