from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table

from vce.db import metadata
from vce.settings import UUID_LENGTH

refresh_token = Table(
    "refresh_token",
    metadata,
    Column("jti", String(UUID_LENGTH), primary_key=True),
    Column("user_id", Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("family_id", String(UUID_LENGTH), nullable=False, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
)
