from sqlalchemy.orm import registry, relationship

from vce.auth.domain import RefreshToken
from vce.auth.orm import refresh_token_table
from vce.coin.domain import Coin
from vce.coin.orm import coin_table
from vce.db import metadata
from vce.user.domain import User
from vce.user.orm import user_table

mapper_registry = registry(metadata=metadata)


def start_orm_mappers():
    """Map the domain classes to their tables. Must run before any ORM use (done in the app lifespan)."""
    if mapper_registry.mappers:
        return
    mapper_registry.map_imperatively(Coin, coin_table)
    mapper_registry.map_imperatively(
        User,
        user_table,
        properties={
            "refresh_tokens": relationship(
                RefreshToken,
                back_populates="user",
                cascade="all, delete-orphan",
                passive_deletes=True,
                lazy="raise",
            ),
        },
    )
    mapper_registry.map_imperatively(
        RefreshToken,
        refresh_token_table,
        properties={"user": relationship(User, back_populates="refresh_tokens", lazy="raise")},
    )
