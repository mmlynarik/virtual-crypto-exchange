from httpx import AsyncClient, HTTPError
from pydantic import BaseModel

from vce.auth.exceptions import GithubAuthError
from vce.settings import (
    GITHUB_CLIENT_ID,
    GITHUB_CLIENT_SECRET,
    GITHUB_NAME_MAX_LENGTH,
    GITHUB_TOKEN_URL,
    GITHUB_USER_URL,
)


class GithubUser(BaseModel):
    id: int
    name: str


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


async def get_github_user(client: AsyncClient, access_token: str) -> GithubUser:
    try:
        res = await client.get(
            GITHUB_USER_URL,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"},
        )
        res.raise_for_status()
    except HTTPError as e:
        raise GithubAuthError(f"GitHub user request failed: {e}") from e

    data = res.json()
    # GitHub names can be longer than the user.github_name column
    return GithubUser(id=data["id"], name=(data.get("name") or data["login"])[:GITHUB_NAME_MAX_LENGTH])
