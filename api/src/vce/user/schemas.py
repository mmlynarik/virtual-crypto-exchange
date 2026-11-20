from pydantic import BaseModel


class UserCreateByEmail(BaseModel):
    email: str
    password: str
    salt: str


class UserCreateByGithub(BaseModel):
    github_id: int
    github_name: str


class UserCreated(BaseModel):
    id: int
