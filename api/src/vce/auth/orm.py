from sqlalchemy import UUID, Column, DateTime, ForeignKey, Table, Text, func

from vce.db import metadata

refresh_token = Table(
    "refresh_token",
    metadata,
    Column("jti", UUID(as_uuid=True), primary_key=True),
    Column(
        "user_id", UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    ),
    Column("family_id", UUID(as_uuid=True), nullable=False, index=True),
    Column("token", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("expires_at", DateTime(timezone=True), nullable=False),
)
