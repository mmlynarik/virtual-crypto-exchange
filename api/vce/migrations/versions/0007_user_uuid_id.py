"""Use UUIDv7 for user.id

Existing users get a fresh UUIDv7 each. All refresh tokens are deleted: every JWT issued so far carries
an integer userId that no longer resolves, so all sessions end and users have to log in again.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-23

"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _drop_refresh_token_user_id() -> None:
    op.execute("DELETE FROM refresh_token")
    op.drop_constraint("refresh_token_user_id_fkey", "refresh_token", type_="foreignkey")
    op.drop_index("ix_refresh_token_user_id", table_name="refresh_token")
    op.drop_column("refresh_token", "user_id")


def _add_refresh_token_user_id(type_: sa.types.TypeEngine) -> None:
    # The table is empty at this point, so the NOT NULL column needs no default
    op.add_column("refresh_token", sa.Column("user_id", type_, nullable=False))
    op.create_index("ix_refresh_token_user_id", "refresh_token", ["user_id"], unique=False)
    op.create_foreign_key(
        "refresh_token_user_id_fkey", "refresh_token", "user", ["user_id"], ["id"], ondelete="CASCADE"
    )


def upgrade() -> None:
    _drop_refresh_token_user_id()

    # PostgreSQL 15 has no uuidv7(), so the ids are generated here
    op.add_column("user", sa.Column("new_id", sa.UUID(), nullable=True))
    bind = op.get_bind()
    for old_id in bind.execute(sa.text('SELECT id FROM "user" ORDER BY id')).scalars():
        bind.execute(
            sa.text('UPDATE "user" SET new_id = :new_id WHERE id = :old_id'),
            {"new_id": uuid.uuid7(), "old_id": old_id},
        )
    op.alter_column("user", "new_id", nullable=False)
    op.drop_constraint("user_pkey", "user", type_="primary")
    op.drop_column("user", "id")  # also drops the user_id_seq sequence it owns
    op.alter_column("user", "new_id", new_column_name="id")
    op.create_primary_key("user_pkey", "user", ["id"])

    _add_refresh_token_user_id(sa.UUID())


def downgrade() -> None:
    # Users get new integer ids; the UUIDs are lost
    _drop_refresh_token_user_id()

    op.drop_constraint("user_pkey", "user", type_="primary")
    op.alter_column("user", "id", new_column_name="uuid_id")
    op.execute('ALTER TABLE "user" ADD COLUMN id SERIAL')  # numbers the existing rows
    op.drop_column("user", "uuid_id")
    op.create_primary_key("user_pkey", "user", ["id"])

    _add_refresh_token_user_id(sa.Integer())
