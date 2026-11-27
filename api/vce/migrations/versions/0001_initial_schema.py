"""Initial schema: cg_coin and user tables

This is the schema that existed before Alembic, when tables were created with metadata.create_all().

Revision ID: 0001
Revises:
Create Date: 2026-11-20

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "coin",
        sa.Column("id", sa.String(length=256), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=True),
        sa.Column("symbol", sa.String(length=30), nullable=True),
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("market_cap", sa.Float(), nullable=True),
        sa.Column("circulating_supply", sa.Float(), nullable=True),
        sa.Column("total_supply", sa.Float(), nullable=True),
        sa.Column("max_supply", sa.Float(), nullable=True),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=256), nullable=True),
        sa.Column("password", sa.String(length=256), nullable=True),
        sa.Column("salt", sa.String(length=64), nullable=True),
        sa.Column("github_id", sa.Integer(), nullable=True),
        sa.Column("github_name", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("user")
    op.drop_table("coin")
