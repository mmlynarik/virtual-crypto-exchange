class UserAlreadyExists(Exception):
    pass


class CannotLinkGithub(Exception):
    """The user already has a GitHub account, or has no password to confirm the link with."""


class WrongPassword(Exception):
    """The password doesn't match, or the user has no password to match."""
