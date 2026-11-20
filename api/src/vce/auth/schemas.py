from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class EmailCredentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginCredentials(BaseModel):
    # Plain str on purpose: EmailStr normalizes the address (e.g. lowercases the domain), which could
    # make an exact-match lookup miss users created before the backend owned registration.
    email: str
    password: str


class GithubCode(BaseModel):
    code: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


class RegisterResponse(TokenPair):
    user_id: int


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str | None
    github_id: int | None
    github_name: str | None
