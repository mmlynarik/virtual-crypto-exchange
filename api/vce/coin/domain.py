from datetime import datetime


class CGCoin:
    """CoinGecko coin market data"""

    def __init__(
        self,
        id: str,
        name: str,
        symbol: str,
        current_price: float | None,
        market_cap: float | None,
        circulating_supply: float | None,
        total_supply: float | None,
        max_supply: float | None,
        last_updated: datetime | None,
    ):
        self.id = id
        self.name = name
        self.symbol = symbol
        self.current_price = current_price
        self.market_cap = market_cap
        self.circulating_supply = circulating_supply
        self.total_supply = total_supply
        self.max_supply = max_supply
        self.last_updated = last_updated

    def __repr__(self) -> str:
        return f"CGCoin(id={self.id!r}, symbol={self.symbol!r}, current_price={self.current_price!r})"
