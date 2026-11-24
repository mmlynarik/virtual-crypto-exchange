"""Store refresh token jti and family_id as native UUIDs

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-23

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = ("jti", "family_id")


def upgrade() -> None:
    for column in COLUMNS:
        op.alter_column(
            "refresh_token",
            column,
            existing_type=sa.String(length=36),
            type_=sa.UUID(),
            existing_nullable=False,
            postgresql_using=f"{column}::uuid",
        )


def downgrade() -> None:
    for column in COLUMNS:
        op.alter_column(
            "refresh_token",
            column,
            existing_type=sa.UUID(),
            type_=sa.String(length=36),
            existing_nullable=False,
            postgresql_using=f"{column}::text",
        )
