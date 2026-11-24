"""Make user email and github_id unique, widen github_id to BIGINT

Fails if the table already has duplicate emails or GitHub ids; resolve those first.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-20

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "user", "github_id", existing_type=sa.Integer(), type_=sa.BigInteger(), existing_nullable=True
    )
    op.create_unique_constraint("uq_user_email", "user", ["email"])
    op.create_unique_constraint("uq_user_github_id", "user", ["github_id"])


def downgrade() -> None:
    op.drop_constraint("uq_user_github_id", "user", type_="unique")
    op.drop_constraint("uq_user_email", "user", type_="unique")
    # Fails if a stored GitHub id no longer fits in INTEGER
    op.alter_column(
        "user", "github_id", existing_type=sa.BigInteger(), type_=sa.Integer(), existing_nullable=True
    )
