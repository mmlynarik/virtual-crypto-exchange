"""Drop user.github_name

GitHub logins now store the account's primary verified email in user.email instead. GitHub users registered
before this get their email filled in on their next GitHub login.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-23

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("user", "github_name")


def downgrade() -> None:
    # The dropped names are not restored
    op.add_column("user", sa.Column("github_name", sa.String(length=64), nullable=True))
