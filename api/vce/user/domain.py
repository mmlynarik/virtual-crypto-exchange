from datetime import datetime
from uuid import UUID


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

    @property
    def can_link_github(self) -> bool:
        """A password account without a GitHub account yet. Linking one needs the password confirmed."""
        return self.github_id is None and self.password is not None

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, email={self.email!r}, github_id={self.github_id!r})"


def normalize_email(email: str) -> str:
    """Emails are case-insensitive here: stored lowercase, and every incoming address is lowercased before
    it's compared or saved. The user table enforces it with a CHECK constraint (migration 0004)."""
    return email.strip().lower()
