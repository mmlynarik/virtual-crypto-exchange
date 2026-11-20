from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table

from vce.db import metadata

# Whitelist of valid refresh tokens; a token is usable only while its row exists
refresh_token = Table(
    "refresh_token",
    metadata,
    Column("jti", String(36), primary_key=True),
    Column("user_id", Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("family_id", String(36), nullable=False, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
)
