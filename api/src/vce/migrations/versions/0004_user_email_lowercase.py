"""Store user emails lowercase

Emails are compared case-insensitively by storing them lowercase. Fails without changing anything if two
users' emails differ only in case: decide which account to keep and fix those rows by hand first.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-20

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conflicts = (
        op.get_bind()
        .execute(
            sa.text(
                'SELECT lower(email) FROM "user" WHERE email IS NOT NULL '
                "GROUP BY lower(email) HAVING count(*) > 1"
            )
        )
        .scalars()
        .all()
    )
    if conflicts:
        raise RuntimeError(
            f"Users whose emails differ only in case, resolve them before migrating: {', '.join(conflicts)}"
        )

    op.execute('UPDATE "user" SET email = lower(email) WHERE email <> lower(email)')
    op.create_check_constraint("ck_user_email_lowercase", "user", "email = lower(email)")


def downgrade() -> None:
    # The emails' original case is gone; only the constraint is removed
    op.drop_constraint("ck_user_email_lowercase", "user", type_="check")
