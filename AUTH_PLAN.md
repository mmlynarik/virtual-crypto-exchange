# Plan: Auth endpoints in the FastAPI backend, with refresh token rotation

## Context
Today the Next.js app (`web/`) does all of the auth work. It hashes and checks passwords with scrypt (`web/src/lib/auth/passwordHasher.ts`), exchanges the GitHub OAuth code (`web/src/lib/auth/user.ts`) and signs HS256 JWTs (`web/src/lib/auth/jwtSession.ts`). FastAPI only stores users, and its `GET /users/email/{email}` returns the password hash and salt so that web can check them. Refresh tokens are fully stateless, so they can't be revoked, and a stolen one stays valid for 7 days.

The goal is to make FastAPI the auth authority:
- Endpoints for password login, GitHub OAuth login, registration, refresh, logout and current user.
- Tokens are returned in the JSON response body. The Next.js server will later read them and set the httpOnly cookies itself.
- **Refresh token rotation backed by a whitelist in the database.** Each refresh token can be used once, using it revokes it, and reusing a revoked token kills the whole session.

**This round changes the backend only.** `web/` is not touched, and the existing `/users/*` endpoints stay because web still uses them.

## Compatibility with existing data and tokens
- **Password hashes:** Node's `crypto.scrypt(pw.normalize(), saltHexString, 64)` uses N=16384, r=8, p=1, and the salt is the UTF‑8 bytes of the hex string. The Python version is `hashlib.scrypt(unicodedata.normalize("NFC", pw).encode(), salt=salt.encode(), n=16384, r=8, p=1, dklen=64).hex()`, compared with `hmac.compare_digest`. Users who already exist can log in through the new endpoint.
- **JWTs:** same secret (`JWT_SECRET_KEY` as UTF‑8 bytes), HS256, claims `userId`, `aud="vce"`, `iat` and `exp`, and the same 5 min / 7 day expiry. New claims:
  - `type` (`access` or `refresh`), on every token.
  - `jti` (a uuid7 that identifies the token) and `fam` (a uuid7 that identifies the session), on refresh tokens only.

  Web's zod schema ignores extra keys, so web's middleware still accepts tokens issued by the backend.

## How rotation and revocation work
- **Whitelist table `refresh_token`:**
  - Columns: `jti` (String(36), primary key), `user_id` (FK to `user.id`, `ON DELETE CASCADE`), `family_id` (String(36), indexed), `created_at` and `expires_at` (timezone-aware DateTime).
  - A row existing means the token is valid. Only the `jti` is stored, not the token itself. The JWT signature already ties the token to its `jti`, so storing the full token adds nothing.
- **Login, register and GitHub login:** each one starts a new family (a new `family_id`), issues an access + refresh pair, and inserts the refresh row.
- **`/auth/refresh`:**
  1. Decode the JWT and check the signature, `aud`, `exp` and `type == "refresh"`. If any check fails → 401 and nothing changes in the DB.
  2. Consume the token atomically: `DELETE FROM refresh_token WHERE jti = :jti RETURNING *`. If two refreshes race, only one of them gets the row.
  3. If no row came back, the token was already rotated or revoked, so it is being reused. Delete every row with that `family_id`, commit, log a warning, and return 401. Both the attacker and the real user lose that session; other sessions (other devices) are unaffected.
  4. Otherwise, issue a new pair in the same family, insert the new row, delete expired rows for that user (cleanup as we go), commit, and return the pair. The response **always** includes a new `refresh_token`.
- **`/auth/logout`:** takes a refresh token and deletes its family, so that session ends. Logout is idempotent: an invalid token or one that was already revoked still returns 204.
- **Access tokens stay stateless.** After a revocation, an access token that was already issued remains valid for at most 5 minutes. That's the usual trade-off; it avoids a DB lookup on every request.
- **Known trade-off with strict rotation:** if the client sends two refreshes with the same token concurrently (for example, Next.js middleware running on parallel requests), the second one counts as reuse and logs the user out. When web is migrated, it should run only one refresh at a time. I'm not adding a grace window now.

## Endpoints (`/api/auth/...`)
| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| POST | `/auth/register` | `{email, password}` (`EmailCredentials`) | 201 `RegisterResponse` `{user_id, access_token, refresh_token, token_type}`. **Creates the `user` row** (salt + scrypt hash) and starts a session, so the new user is logged in straight away | 409 email exists, 422 invalid email or password shorter than 8 characters (rejected by Pydantic validation) |
| POST | `/auth/login` | `{email, password}` (`LoginCredentials`) | 200 `TokenPair` | 401 "Incorrect email or password" (also returned for GitHub-only users with no password) |
| POST | `/auth/github` | `{code}` | 200 `TokenPair`; creates the user on first login | 401 when the GitHub code exchange fails |
| POST | `/auth/refresh` | `{refresh_token}` | 200 `TokenPair` (both tokens new) | 401 when the token is invalid, expired, the wrong type, or reused (reuse also revokes the family) |
| POST | `/auth/logout` | `{refresh_token}` | 204 | none (idempotent) |
| GET | `/auth/me` | `Authorization: Bearer <access>` | 200 `UserPublic` (id, email, github_id, github_name) | 401 |

`TokenPair = {access_token, refresh_token, token_type: "bearer"}`.

## Changes

**Step 0, before any code changes:** save a copy of this plan as `AUTH_PLAN.md` in the repo root (`/home/miro/Projects/wsl/virtual-crypto-exchange/AUTH_PLAN.md`).

**`api/pyproject.toml`**: `uv add pyjwt`.

**`api/src/vce/settings.py`**: add `JWT_SECRET_KEY` (from env; raise an error if it's missing), `JWT_ALGORITHM="HS256"`, `JWT_AUDIENCE="vce"`, `JWT_ACCESS_TOKEN_EXPIRY_SECONDS=300`, `JWT_REFRESH_TOKEN_EXPIRY_SECONDS=7*24*3600`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_TOKEN_URL`, `GITHUB_USER_URL`.

**`api/src/vce/auth.py`** (new domain module):
- **Pydantic models** (`BaseModel`) for every request and response body:
  - `EmailCredentials`: `email: EmailStr` and `password: str = Field(min_length=8)`. FastAPI rejects passwords that are too short or malformed emails with a 422 before the service is called. `email-validator` is already installed through `fastapi[standard]`.
  - `LoginCredentials`: `email: EmailStr` and `password: str`, with no minimum length, so an old password that's under 8 characters still reaches the check and gets the generic 401.
  - `GithubCode`: `code: str`.
  - `RefreshRequest`: `refresh_token: str`.
  - `TokenPair`: `access_token`, `refresh_token` and `token_type: Literal["bearer"] = "bearer"`.
  - `RegisterResponse(TokenPair)`: adds `user_id: int`.
  - `UserPublic`: `id`, `email`, `github_id` and `github_name`, with `model_config = ConfigDict(from_attributes=True)` and built with `UserPublic.model_validate(user)`. It never includes `password` or `salt`.
  - `GithubUser`: `id: int` and `name: str` (in `github.py`).
- **A plain dataclass** for `RefreshToken(jti, user_id, family_id, created_at, expires_at)` only, because it's mapped imperatively in `orm.py` like `User` and `CGCoin`.
- Exceptions: `InvalidCredentials`, `InvalidToken`, `RefreshTokenReused`, `GithubAuthError`. `PasswordTooShort` isn't needed, because the `Field` constraint covers it.
- `generate_salt()` (`secrets.token_hex(16)`), `hash_password(pw, salt)` and `verify_password(pw, hashed, salt)`, all Node-compatible as described above.
- `create_access_token(user_id)`.
- `create_refresh_token(user_id, family_id) -> (token, RefreshToken record)`.
- `decode_token(token, expected_type) -> payload`: wraps PyJWT errors in `InvalidToken` and checks the audience and type.

**`api/src/vce/orm.py`**: add the `refresh_token` table, mapped imperatively to `RefreshToken` the same way `cg_coin` and `user` are. `create_db_and_tables()` creates it automatically at startup.

**`api/src/vce/repository.py`**: add `RefreshTokenRepository(session)` with these methods:
- `add(token)`
- `consume(jti) -> RefreshToken | None`, using `delete(...).where(jti==...).returning(...)`
- `revoke_family(family_id)`
- `delete_expired_for_user(user_id)`

**`api/src/vce/github.py`** (new; follows the style of `coingecko.py`):
- `exchange_code_for_token(client, code)`: POST to `GITHUB_TOKEN_URL` with `Accept: application/json`. GitHub returns 200 with an `error` field when the code is bad, so that case raises `GithubAuthError`.
- `get_github_user(client, token) -> GithubUser` (a Pydantic model), with `name` falling back to `login` when it is null.
- Both use absolute URLs on the shared `AsyncClient`, whose `base_url` is CoinGecko. httpx sends absolute URLs as they are.

**`api/src/vce/services.py`** (reuses the existing `UsersRepository`, `register_user_by_email`, `register_user_by_github` and `get_user_by_*`):
- `start_session(user_id, token_repo, session) -> TokenPair`: creates a new family, issues the pair, inserts the row and commits.
- `register_with_password(creds: EmailCredentials, ...) -> RegisterResponse`:
  1. Generate a salt and hash the password. The length is already checked by Pydantic.
  2. **Create the user** with the existing `register_user_by_email`, which raises `UserAlreadyExists` → 409.
  3. Call `start_session(user.id)` and return the user id together with the tokens.
- `login_with_password(creds: LoginCredentials, ...)`: `repo.get_by_email` → `InvalidCredentials` if there's no user or `password` is None → `verify_password` → `start_session`.
- `login_with_github(code, ...)`: exchange the code, fetch the GitHub user, `get_user_by_github_id`, and fall back to `register_user_by_github` if the user doesn't exist → `start_session`.
- `rotate_refresh_token(refresh_token, ...)`: the refresh flow described above. Raises `RefreshTokenReused` after revoking the family.
- `logout(refresh_token, ...)`: decode the token (return quietly if it's invalid), then `revoke_family` and commit.
- `get_user_from_access_token(token, repo)`.

**`api/src/vce/di.py`**: move `DBSessionDep` and `HTTPClientDep` here from `app.py`, so the new router can import them without a circular import. Add a `get_current_user` dependency that uses `HTTPBearer(auto_error=False)` and raises 401 with `WWW-Authenticate: Bearer`, plus a `CurrentUserDep` alias that future protected endpoints can reuse.

**`api/src/vce/auth_routes.py`** (new): `router = APIRouter(prefix="/auth", tags=["auth"])` with the 6 endpoints. Each one maps domain exceptions to `HTTPException`, the same way `app.py` does.

**`api/src/vce/app.py`**: `app.include_router(auth_router)`, and import the dependency aliases from `di.py`.

**`docker-compose-dev.yaml` / `docker-compose-prod.yaml`**: add `JWT_SECRET_KEY` (the same value as web, because web's middleware verifies the tokens), `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` to the `api` service.

**`api/tests/test_auth.py`** (new; the tests directory is currently empty):
- Tests for the pure functions:
  - Scrypt compatibility against a vector generated with Node (`node -e "crypto.scrypt(...)"`) at implementation time.
  - `verify_password` with right and wrong passwords.
  - Access and refresh tokens round trip; wrong type, wrong audience and expired tokens are rejected.
- Tests for the services, using an in-memory fake `RefreshTokenRepository` and a fake session with an async `commit()`:
  - Rotation returns a new `jti` in the same family and removes the old one.
  - Reusing the old token raises `RefreshTokenReused` and empties the family, so the newest token fails too.
  - Logout revokes the family.
  - Another family for the same user isn't affected by any of the above.

## Verification
1. `cd api && uv run pytest && uv run mypy src && uv run ruff check src`
2. `docker compose -f docker-compose-dev.yaml up --build api db`, then run curl against `localhost:8000/api`:
   - `POST /auth/register` → 201 with `user_id` and tokens. Check that `SELECT * FROM "user"` has the new row with a hashed password and a salt. The same email again → 409.
   - `POST /auth/login` with the right password → 200, with a wrong one → 401. Then log in as a user that web created earlier, to confirm the hashes are compatible.
   - `GET /auth/me` with the access token → user, with the refresh token → 401.
   - `POST /auth/refresh` with token R1 → returns R2. Use R1 again → 401. Then use R2 → 401, because the family was revoked. In the DB, `SELECT * FROM refresh_token` has no rows left for that family.
   - Log in twice to get sessions A and B. Log out A, and B can still refresh.
   - `POST /auth/github` with a junk code → 401. For a real check, open `GITHUB_AUTHORIZE_URL` in a browser, copy the `code` from the callback URL and POST it before web's callback consumes it (or point the redirect somewhere that won't consume it).
3. Paste an access token from the backend into the web cookie to confirm that web's middleware accepts it.

## Follow-ups (out of scope)
- Wire web to `/auth/*`, and make sure it runs only one refresh at a time (see the trade-off above). After that:
  - Remove `/users/email`, which takes a pre-hashed password.
  - Stop `GET /users/*` from returning `password` and `salt`. In prod, the API's port 8000 is published on the host, so those hashes can be read today.
- An optional `/auth/logout-all` endpoint that revokes all of a user's families, for example after a password change.
- GitHub client secrets and the JWT secret are committed in the compose files. Move them to a `.env` file and rotate them.
- Web's `GITHUB_AUTHORIZE_URL` uses `redirect_url` where GitHub expects `redirect_uri`, and the OAuth flow has no `state` parameter, so it isn't protected against CSRF.
