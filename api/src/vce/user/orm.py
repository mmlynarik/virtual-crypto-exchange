from sqlalchemy import (
    UUID,
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    String,
    Table,
    UniqueConstraint,
    func,
)

from vce.db import metadata
from vce.settings import EMAIL_MAX_LENGTH, GITHUB_NAME_MAX_LENGTH

user = Table(
    "user",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("email", String(EMAIL_MAX_LENGTH)),
    Column("password", String(256)),
    Column("salt", String(64)),
    Column("github_id", BigInteger),
    Column("github_name", String(GITHUB_NAME_MAX_LENGTH)),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("email", name="uq_user_email"),
    UniqueConstraint("github_id", name="uq_user_github_id"),
    CheckConstraint("email = lower(email)", name="ck_user_email_lowercase"),
)
