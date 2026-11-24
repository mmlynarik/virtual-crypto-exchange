"""Store the signed refresh token JWT on its whitelist row

Nullable: rows created before this migration have no token to backfill.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-23

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("refresh_token", sa.Column("token", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("refresh_token", "token")
