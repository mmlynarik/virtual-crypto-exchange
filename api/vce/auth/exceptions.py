from fastapi import HTTPException, status


class UnauthorizedError(HTTPException):
    """401 response carrying the WWW-Authenticate header that Bearer auth requires (RFC 6750)."""

    def __init__(self, detail: str = "Not authenticated"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class InvalidCredentials(Exception):
    pass


class InvalidToken(Exception):
    pass


class RefreshTokenReused(Exception):
    pass


class GithubAuthError(Exception):
    pass


class GithubLinkRequired(Exception):
    """The GitHub email belongs to a password account. Confirming its password with the pending link token
    links the GitHub account to it."""

    def __init__(self, email: str, pending_link_token: str):
        super().__init__("GitHub email belongs to a password account")
        self.email = email
        self.pending_link_token = pending_link_token


class GithubAlreadyLinked(Exception):
    """Redeeming a pending link token found the account already linked to a GitHub account, or the GitHub
    account already linked to another account."""


class GithubEmailTaken(Exception):
    """The GitHub email belongs to an account that can't be linked, e.g. one linked to another GitHub
    account."""
