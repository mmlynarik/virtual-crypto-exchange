from typing import Annotated, Literal
from uuid import UUID

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


class GithubConflict(BaseModel):
    """Why /auth/github refused with 409. ACCOUNT_EXISTS comes with a pending link token, redeemed with the
    account's password; EMAIL_TAKEN can't be resolved by the user."""

    code: Literal["ACCOUNT_EXISTS", "EMAIL_TAKEN"]
    message: str
    email: str | None = None
    pending_link_token: str | None = None


class GithubConflictResponse(BaseModel):
    """The 409 body of /auth/github, for the OpenAPI docs."""

    detail: GithubConflict


class GithubPendingLinkRequest(BaseModel):
    pending_link_token: str
    password: str = Field(max_length=PASSWORD_MAX_LENGTH)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


class RegisterResponse(TokenPair):
    user_id: UUID


class EmailAvailability(BaseModel):
    available: bool


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str | None
    github_id: int | None
