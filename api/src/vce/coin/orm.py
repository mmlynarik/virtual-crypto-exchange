from sqlalchemy import Column, DateTime, Float, String, Table

from vce.db import metadata

cg_coin = Table(
    "cg_coin",
    metadata,
    Column("id", String(256), primary_key=True),
    Column("name", String(256)),
    Column("symbol", String(30)),
    Column("current_price", Float),
    Column("market_cap", Float),
    Column("circulating_supply", Float),
    Column("total_supply", Float),
    Column("max_supply", Float),
    Column("last_updated", DateTime(timezone=True)),
)
