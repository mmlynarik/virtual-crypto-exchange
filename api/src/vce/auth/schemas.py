from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

from vce.settings import EMAIL_MAX_LENGTH, PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH
from vce.user.domain import normalize_email

NewEmail = Annotated[EmailStr, Field(max_length=EMAIL_MAX_LENGTH), AfterValidator(normalize_email)]
LoginEmail = Annotated[str, Field(max_length=EMAIL_MAX_LENGTH), AfterValidator(normalize_email)]


class EmailRegisterCredentials(BaseModel):
    email: NewEmail
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class EmailLoginCredentials(BaseModel):
    email: LoginEmail
    password: str = Field(max_length=PASSWORD_MAX_LENGTH)


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


class EmailAvailability(BaseModel):
    available: bool


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str | None
    github_id: int | None
    github_name: str | None
