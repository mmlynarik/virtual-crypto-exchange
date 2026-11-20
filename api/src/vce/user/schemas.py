from pydantic import BaseModel, ConfigDict


class UserCreateByEmail(BaseModel):
    email: str
    password: str
    salt: str


class UserCreateByGithub(BaseModel):
    github_id: int
    github_name: str


class UserCreated(BaseModel):
    id: int


class UserResponse(BaseModel):
    """Response for the /users/* endpoints.

    Still includes password and salt because the web app's login reads them from GET /users/email/{email}.
    Drop them once web uses /auth/login.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str | None
    password: str | None
    salt: str | None
    github_id: int | None
    github_name: str | None
