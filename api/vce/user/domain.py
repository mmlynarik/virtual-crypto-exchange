import uuid
from datetime import datetime
from typing import Self
from uuid import UUID

from vce.user.exceptions import CannotLinkGithub, WrongPassword
from vce.utils import generate_salt, hash_password, verify_password


class User:
    def __init__(
        self,
        id: UUID,
        email: str | None,
        password: str | None,
        salt: str | None,
        github_id: int | None,
        created_at: datetime | None = None,
    ):
        self.id = id
        self.email = email
        self.password = password
        self.salt = salt
        self.github_id = github_id
        self.created_at = created_at

    @classmethod
    def from_password(cls, email: str, password: str) -> Self:
        salt = generate_salt()
        return cls(
            id=uuid.uuid7(), email=email, password=hash_password(password, salt), salt=salt, github_id=None
        )

    @classmethod
    def from_github(cls, github_id: int, email: str) -> Self:
        return cls(id=uuid.uuid7(), email=email, password=None, salt=None, github_id=github_id)

    @property
    def can_link_github(self) -> bool:
        """A password account without a GitHub account yet. Linking one needs the password confirmed."""
        return self.github_id is None and self.password is not None

    def link_github(self, github_id: int) -> None:
        """Raises CannotLinkGithub unless can_link_github. The uq_user_github_id constraint, not this method,
        keeps the GitHub account from being linked to two users."""
        if not self.can_link_github:
            raise CannotLinkGithub
        self.github_id = github_id

    def check_password(self, password: str):
        if self.password is None or self.salt is None:
            raise WrongPassword
        if not verify_password(password, self.password, self.salt):
            raise WrongPassword

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, email={self.email!r}, github_id={self.github_id!r})"


def normalize_email(email: str) -> str:
    """Emails are case-insensitive here: stored lowercase, and every incoming address is lowercased before
    it's compared or saved. The user table enforces it with a CHECK constraint (migration 0004)."""
    return email.strip().lower()
