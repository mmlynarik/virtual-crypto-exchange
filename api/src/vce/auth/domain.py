from datetime import datetime
from typing import Literal

TokenType = Literal["access", "refresh"]


class RefreshToken:
    """Whitelist entry: a refresh token is valid only while its row exists"""

    def __init__(self, jti: str, user_id: int, family_id: str, created_at: datetime, expires_at: datetime):
        self.jti = jti
        self.user_id = user_id
        self.family_id = family_id
        self.created_at = created_at
        self.expires_at = expires_at

    def __repr__(self) -> str:
        return (
            f"RefreshToken(jti={self.jti!r}, user_id={self.user_id!r}, family_id={self.family_id!r}, "
            f"expires_at={self.expires_at!r})"
        )
