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
