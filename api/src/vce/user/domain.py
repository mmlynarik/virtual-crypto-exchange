class User:
    def __init__(
        self,
        id: int | None,
        email: str | None,
        password: str | None,
        salt: str | None,
        github_id: int | None,
        github_name: str | None,
    ):
        self.id = id
        self.email = email
        self.password = password
        self.salt = salt
        self.github_id = github_id
        self.github_name = github_name

    def __repr__(self) -> str:
        return (
            f"User(id={self.id!r}, email={self.email!r}, "
            f"github_id={self.github_id!r}, github_name={self.github_name!r})"
        )
