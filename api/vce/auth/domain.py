from datetime import datetime
from typing import Literal
from uuid import UUID

from vce.auth.exceptions import InvalidCredentials
from vce.user.domain import User
from vce.user.exceptions import WrongPassword

TokenType = Literal["access", "refresh", "github_pending_link"]


class RefreshToken:
    """Whitelist entry. A refresh token is valid only while its row exists"""

    def __init__(
        self,
        jti: UUID,
        user_id: UUID,
        family_id: UUID,
        token: str,
        expires_at: datetime,
        created_at: datetime | None = None,
    ):
        self.jti = jti
        self.user_id = user_id
        self.family_id = family_id
        self.created_at = created_at
        self.expires_at = expires_at
        self.token = token

    def __repr__(self) -> str:
        return (
            f"RefreshToken(jti={self.jti!r}, user_id={self.user_id!r}, family_id={self.family_id!r}, "
            f"expires_at={self.expires_at!r})"
        )


def authenticate(user: User | None, password: str) -> User:
    """
    The one place passwords are checked (password login and GitHub linking), so throttling added here
    later covers every endpoint that takes a password. Raises InvalidCredentials for a missing user, an
    account without a password, or a wrong password alike, so a response doesn't tell which.
    """
    if user is None:
        raise InvalidCredentials
    try:
        user.check_password(password)
    except WrongPassword as e:
        raise InvalidCredentials from e
    return user
