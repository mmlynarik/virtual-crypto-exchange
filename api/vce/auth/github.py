from httpx import AsyncClient, HTTPError
from pydantic import BaseModel

from vce.auth.exceptions import GithubAuthError
from vce.settings import (
    EMAIL_MAX_LENGTH,
    GITHUB_CLIENT_ID,
    GITHUB_CLIENT_SECRET,
    GITHUB_EMAILS_URL,
    GITHUB_TOKEN_URL,
    GITHUB_USER_URL,
)
from vce.user.domain import normalize_email


class GithubUser(BaseModel):
    id: int
    email: str


async def exchange_code_for_token(client: AsyncClient, code: str) -> str:
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise RuntimeError("Missing GITHUB_CLIENT_ID or GITHUB_CLIENT_SECRET env variable")
    try:
        res = await client.post(
            GITHUB_TOKEN_URL,
            params={"client_id": GITHUB_CLIENT_ID, "client_secret": GITHUB_CLIENT_SECRET, "code": code},
            headers={"Accept": "application/json"},
        )
        res.raise_for_status()
    except HTTPError as e:
        raise GithubAuthError(f"GitHub token request failed: {e}") from e

    # GitHub answers 200 with an "error" field for bad/expired codes
    data = res.json()
    access_token = data.get("access_token")
    if not access_token:
        raise GithubAuthError(data.get("error_description") or data.get("error") or "No access token")
    return access_token


async def get_from_github(client: AsyncClient, url: str, access_token: str):
    try:
        res = await client.get(
            url, headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"}
        )
        res.raise_for_status()
    except HTTPError as e:
        raise GithubAuthError(f"GitHub request to {url} failed: {e}") from e
    return res.json()


async def get_github_user(client: AsyncClient, access_token: str) -> GithubUser:
    """The GitHub account id and its primary email. The email comes from /user/emails (needs the
    user:email scope) rather than /user, which only shows an email the user chose to make public."""
    data = await get_from_github(client, GITHUB_USER_URL, access_token)
    emails = await get_from_github(client, GITHUB_EMAILS_URL, access_token)

    primary = next((e for e in emails if e.get("primary") and e.get("verified")), None)
    if primary is None:
        raise GithubAuthError("GitHub account has no verified primary email")
    email = normalize_email(primary["email"])
    if len(email) > EMAIL_MAX_LENGTH:
        raise GithubAuthError("GitHub primary email is too long")
    return GithubUser(id=data["id"], email=email)
