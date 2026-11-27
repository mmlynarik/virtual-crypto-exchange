---
name: fastapi-router
description: Architectural rules for FastAPI routes in the vce API, taken from the auth domain (vce/auth/router.py), which is the reference implementation. Use when adding, changing, reviewing or testing an endpoint or a domain's router.py, mapping domain exceptions to HTTP errors, adding a dependency such as UnitOfWork, CoinClient, GithubClient or CurrentUser, choosing status codes or response bodies, or writing request/response schemas.
---

# FastAPI routes

`vce/auth/router.py` is the reference. Read it next to this file before you write a route. The coin
router predates these rules (see "Known deviations"); don't copy its patterns.

## 1. Layout and wiring

- Each domain package (`vce/<domain>/`) owns one `router.py`, next to its `services.py`, `schemas.py`,
  `exceptions.py` and `dependencies.py`.
- A router declares its own prefix and OpenAPI tag: `router = APIRouter(prefix="/auth", tags=["auth"])`.
  Paths inside are relative (`/login`, `/github/link-pending`). Use kebab-case for multi-word paths.
- `vce/app.py` only does `app.include_router(...)`. The app has `root_path="/api"`, so don't put `/api`
  into routes.
- App-wide resources (the sessionmaker, one `httpx.AsyncClient` per upstream API) are created in the `lifespan` in
  `app.py` and read from `request.state` by dependencies. Routes never create clients, engines or
  sessions.

## 2. Routes are thin: HTTP in, one service call, HTTP out

A route does exactly three things:
1. It takes validated input (a schema, a query parameter or a dependency).
2. It calls **one** service function and passes the unit of work in **unopened**.
3. It turns the result into a response schema, or a domain exception into an `HTTPException`.

These belong in services and domain classes, not in routes: business rules, repository access,
`async with uow:`, commits, token handling, external API calls.

```python
@router.post("/login")
async def login(creds: EmailLoginCredentials, uow: UnitOfWork) -> TokenPair:
    try:
        return await services.login_with_password(creds, uow)
    except InvalidCredentials:
        raise UnauthorizedError("Incorrect email or password")
```

- Import the services **as a module** (`from vce.auth import services`) and call
  `services.login_with_password(...)`. The router tests monkeypatch `router.services.<fn>`. Importing
  the function by name would bypass the patch.
- Transactions belong to the service, which opens `async with uow:` and commits explicitly, one use
  case per transaction (see `vce/uow.py`). The route never commits or rolls back.

## 3. Dependencies

Write every injected value as an `Annotated` alias, so a route signature reads `uow: UnitOfWork`, not
`Depends(...)`:

| Alias | Defined in | Gives |
|---|---|---|
| `UnitOfWork` | `vce/dependencies.py` | a fresh, unopened `SqlAlchemyUnitOfWork` |
| `CoinClient` | `vce/dependencies.py` | the lifespan's CoinGecko `httpx.AsyncClient` (base URL `COIN_API_URL`) |
| `GithubClient` | `vce/dependencies.py` | the lifespan's GitHub API `httpx.AsyncClient` (base URL `GITHUB_API_URL`, GitHub `Accept` header) |
| `CurrentUser` | `vce/auth/dependencies.py` | the authenticated `User`, or a 401 |

- A new shared dependency goes in `vce/dependencies.py`. A dependency used by one domain goes in that
  domain's `dependencies.py`. Both follow the same pattern: a getter function plus an `Annotated[...,
  Depends(getter)]` alias.
- **Protected route**: add `user: CurrentUser`. That's all the auth a route does. `get_current_user`
  reads the user in its **own** unit of work and returns it **detached**. You can read its columns, but
  changes to it are never saved. If the use case modifies the user, pass `user.id` to the service and
  reload the user inside the service's unit of work.
- `HTTPBearer(auto_error=False)` is deliberate. FastAPI's default sends 403 when the header is missing.
  We send our own 401 with `WWW-Authenticate: Bearer` instead (RFC 6750). The web client treats any
  401 as "session over, log out".

## 4. Errors: domain exceptions become HTTP errors only in the router

- Services and domain code raise **plain exceptions** (`class InvalidToken(Exception)`) from
  `<domain>/exceptions.py`. They don't know about HTTP and never raise `HTTPException`. A docstring
  says when the exception happens, if the name doesn't.
- The route catches each expected exception and raises the HTTP error, without `from e` (the domain
  exception is not part of the API). Let anything unexpected propagate as a 500.
- Group exceptions that map to the same response in one `except`, with the Python 3.14 form
  (PEP 758) that the codebase uses: `except GithubEmailTaken, UserAlreadyExists:`.

Status code mapping:

| Situation | Status | How |
|---|---|---|
| Bad, missing, expired or reused credentials or tokens | 401 | `raise UnauthorizedError("...")`. Never a bare `HTTPException(401)`: `UnauthorizedError` adds `WWW-Authenticate: Bearer`. |
| Resource already exists, or the state conflicts (email taken, already linked) | 409 | `HTTPException(status_code=409, detail=...)` |
| Malformed input | 422 | Leave it to pydantic: put the constraint on the schema, not in an `if` in the route. |
| Not found | 404 | `HTTPException(status_code=404, detail=...)` |

**What a 401 may say**: never tell the client *which* part of the credentials failed. An unknown
email, an account with no password and a wrong password all give `"Incorrect email or password"`.
Distinct messages are fine only when they reveal nothing about accounts, e.g. "Refresh token has
already been used; session revoked" vs. "Invalid refresh token".

**Log what you hide**: when the route swaps a detailed error for a generic message, log the detail on
the server, e.g. `LOGGER.warning("GitHub login rejected: %s", e)` before
`UnauthorizedError("GitHub authentication failed")`. Successful outcomes are logged by the service,
not the route.

## 5. Structured error bodies, when the client must branch

A plain `detail: str` is enough when the client only needs the status. When one status covers several
outcomes that the client handles differently (e.g. `/auth/github`'s 409 is either "enter your password
to link" or "nothing you can do"), use a **typed body**:

```python
class GithubConflict(BaseModel):            # schemas.py
    code: Literal["ACCOUNT_EXISTS", "EMAIL_TAKEN"]
    message: str                            # human-readable, shown by the UI
    email: str | None = None                # fields some codes need
    pending_link_token: str | None = None

class GithubConflictResponse(BaseModel):    # only for OpenAPI
    detail: GithubConflict
```

```python
def github_conflict(conflict: GithubConflict) -> HTTPException:
    return HTTPException(status_code=409, detail=conflict.model_dump(exclude_none=True))

@router.post("/github", responses={409: {"model": GithubConflictResponse}})
```

- Keep the body under `detail`, like every other error of the API, so clients read errors one way.
- `code` is a `Literal`, a stable machine-readable value. `message` is for people. Fields that only
  some codes need are optional and left out with `exclude_none=True`.
- Document the body with `responses={status: {"model": ...Response}}` and a wrapper model with a
  `detail` field.
- Build the exception with a small helper (`github_conflict`) when several branches share the body
  shape.

## 6. Requests and responses

- **Response type = return annotation.** Write `-> TokenPair` and let FastAPI validate, serialize and
  document it. Don't add `response_model=`.
- **Return schemas, never domain or ORM objects.** Convert explicitly:
  `UserPublic.model_validate(user)`, with `model_config = ConfigDict(from_attributes=True)` on the
  schema. This keeps password hashes and salts out of responses, which is why the old `/users/*` routes
  were removed.
- Response schemas can extend each other when one response is another plus fields:
  `class RegisterResponse(TokenPair): user_id: UUID`.
- **Bodies are always a model**, even for one field (`GithubCode`, `RefreshRequest`). Secrets such as
  passwords, refresh tokens, OAuth codes and link tokens go in a POST body, never in the path or query
  string, where they would end up in access logs.
- **Query parameters** are only for read-only GETs with simple inputs:
  `email: Annotated[NewEmail, Query()]`. Reuse the **same annotated type** that the related body uses.
  `/email-available` uses `NewEmail`, as `/register` does, so both normalize the address the same way.
- **Validation lives on reusable annotated types** in `schemas.py`, with limits from `vce/settings.py`
  that the table uses too (`EMAIL_MAX_LENGTH`, `PASSWORD_MAX_LENGTH`). Validate input more strictly
  when it creates data than when it looks data up:
  - `NewEmail` is an `EmailStr` that is normalized. Registration has a password minimum.
  - `LoginEmail` is a plain `str` with a max length. A login password has only a max length (a cap
    against hashing very long inputs).
  - So an odd but stored address still gets a 401 at login, not a 422.

## 7. Status codes and methods

- Actions (login, register, refresh, link, logout) are `POST`. Reads with no side effects (`/me`,
  `/email-available`) are `GET`.
- Creating something: `status_code=status.HTTP_201_CREATED` in the decorator.
- No body: `status_code=status.HTTP_204_NO_CONTENT` in the decorator, **and** return
  `Response(status_code=status.HTTP_204_NO_CONTENT)` with the return type `-> Response`.
- Use the `fastapi.status` constants in decorators. Literal numbers are accepted in
  `HTTPException(status_code=409, ...)`.
- Make an endpoint **idempotent and quiet** when failing would tell the client nothing useful.
  `/logout` sends 204 even for an invalid or expired refresh token: the service swallows
  `InvalidToken`, and the client clears its cookies anyway.

## 8. Docstrings

Add a docstring only when a route takes part in a flow across endpoints, or has a non-obvious reason,
e.g. `link_github_pending` ("Link GitHub to the account that /auth/github answered ACCOUNT_EXISTS
for...") or `email_available` ("Takes the email the same way /register does"). FastAPI shows it in
OpenAPI. Self-explanatory routes have none.

## 9. Testing routes

Test the logic on the services with `FakeUnitOfWork` (`tests/fakes.py`). Test the **router itself only
for its mapping**: call the endpoint function directly, with the service monkeypatched to raise the
domain exception:

```python
@pytest.mark.parametrize(
    "raised, status",
    [(InvalidToken("expired"), 401), (InvalidCredentials(), 401), (GithubAlreadyLinked(), 409)],
)
def test_link_pending_router_errors(monkeypatch, raised, status):
    async def link_github_with_password(*args):
        raise raised

    monkeypatch.setattr(auth_router.services, "link_github_with_password", link_github_with_password)
    body = GithubPendingLinkRequest(pending_link_token="token", password="password")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth_router.link_github_pending(body, FakeUnitOfWork()))
    assert exc.value.status_code == status
```

- Import the router as a module: `from vce.auth import router as auth_router`.
- For structured bodies, also assert `detail["code"]`, the fields that code needs, and that fields
  meant to be left out really are (`"pending_link_token" not in error.detail`).
- Test input limits on the schema directly:
  `pytest.raises(ValidationError): GithubPendingLinkRequest(..., password="x" * (MAX + 1))`.
- Write the test first, see it fail, then implement (see `AGENTS.md`).

## Checklist for a new endpoint

- [ ] The route is in `vce/<domain>/router.py`, on a router with `prefix` and `tags`, included in
      `app.py`.
- [ ] Input is a schema from `schemas.py` (or `Annotated[..., Query()]` for a simple GET), and its
      limits come from `settings.py`.
- [ ] The route calls one service, through `services.<fn>`, and passes `uow` unopened. No repository or
      transaction code in the route.
- [ ] Every domain exception the service can raise is mapped: 401 via `UnauthorizedError`, 409 for
      conflicts, a typed `detail` when the client must branch, documented with `responses=`.
- [ ] 401 messages don't tell which credential was wrong. Hidden details are logged.
- [ ] The return annotation is a response schema. Domain objects are converted with `model_validate`.
- [ ] Correct method and status (201 / 204 with `Response`). Secrets only in POST bodies.
- [ ] A protected route takes `user: CurrentUser` and doesn't mutate it.
- [ ] Router tests cover each exception mapping. Service tests cover the logic.

## Known deviations (don't copy)

`vce/coins/router.py` is older:
- It answers 422 for an already existing resource (should be 409).
- `delete_coin_from_id` returns an untyped `{"message": "OK"}` (should be 204).
- It imports the service functions by name.

Follow this skill for new code, and align coins when you touch it, if the change stays in scope.
