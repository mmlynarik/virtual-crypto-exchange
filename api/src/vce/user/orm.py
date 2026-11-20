from sqlalchemy import BigInteger, CheckConstraint, Column, Integer, String, Table, UniqueConstraint

from vce.db import metadata
from vce.settings import EMAIL_MAX_LENGTH, GITHUB_NAME_MAX_LENGTH

user = Table(
    "user",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("email", String(EMAIL_MAX_LENGTH)),
    Column("password", String(256)),
    Column("salt", String(64)),
    Column("github_id", BigInteger),
    Column("github_name", String(GITHUB_NAME_MAX_LENGTH)),
    UniqueConstraint("email", name="uq_user_email"),
    UniqueConstraint("github_id", name="uq_user_github_id"),
    CheckConstraint("email = lower(email)", name="ck_user_email_lowercase"),
)
