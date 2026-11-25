# Plan: link GitHub to an existing email/password account

Status: **backend done** (steps 1–6); frontend not started
Scope: backend (`api/`) only. Frontend changes are listed under [Out of scope](#out-of-scope).

## Problem

A user registers with email + password. Later they click "Continue with GitHub" on the login page, and their
GitHub account's verified primary email is the same address.

Today `/auth/github` refuses with `409 "An account with this GitHub email already exists"`. The user can't
use GitHub at all, and nothing tells them how to connect it.

## Decisions

- **Never merge accounts automatically because the emails match**, even when GitHub reports the email as
  verified. Password signups don't verify their email here. With automatic merging, an attacker could
  pre-register a victim's email with a password, or control a GitHub account that shows that email, and end
  up inside the account.
- **Linking needs proof of both identities**: ownership of the GitHub account (the OAuth code exchange)
  **and** of the existing account (its password).
- **Link right after GitHub login, once the user confirms their password.** The backend has already proven
  the GitHub identity when it finds the email collision, so it hands that proof to the frontend as a
  short-lived signed token. The user then only enters their password. One GitHub round-trip, one password
  prompt.
- **No "connect GitHub" from account settings.** The design discussion described it first, but the flow
  above covers the case this plan is about. Dropped.
- **Later GitHub logins look the user up only by GitHub id**, never by email. This is already the case.

## What already exists

| Piece | Where |
| --- | --- |
| GitHub id + verified primary email from `/user` and `/user/emails` | [auth/github.py](../vce/auth/github.py) |
| GitHub login looks the user up by `github_id` first | `login_with_github` in [auth/services.py](../vce/auth/services.py) |
| One account per GitHub id (`uq_user_github_id`) and per email (`uq_user_email`) | [user/orm.py](../vce/user/orm.py) |
| GitHub registration refuses an email that is already used (`UserAlreadyExists` → 409) | `register_user_by_github` in [user/services.py](../vce/user/services.py) |
| Password registration refuses an email that is already used (409) | `/auth/register` in [auth/router.py](../vce/auth/router.py) |
| Signed JWTs with an enforced `type` claim | `encode_jwt` / `decode_token` in [auth/security.py](../vce/auth/security.py) |

## Target flow

```
User (not logged in)                                Backend
────────────────────                                ───────
"Continue with GitHub" → GitHub → back with ?code
  ────────────────────────────────────────────────▶ POST /auth/github { code }
                                                     code exchange → githubId 12345678, alice@example.com
                                                     no user with this github_id; email belongs to user U
                                                     (U has no github_id)
                    ◀──────────────────────────── 409 { code: ACCOUNT_EXISTS, email,
                                                          pending_link_token (U, 12345678, 10 min) }
  "An account with this email exists.
   Enter your password to connect GitHub."
  ────────────────────────────────────────────────▶ POST /auth/github/link-pending
                                                     { pending_link_token, password }
                                                     verify token + password, set U.github_id
                    ◀──────────────────────────── 200 TokenPair (logged in)

Later: "Continue with GitHub" ────────────────────▶ POST /auth/github → found by github_id → TokenPair
```

## Steps

### 1. Pending link token

Files: `auth/domain.py`, `auth/security.py`, `settings.py`

- [x] Add `"github_pending_link"` to `TokenType`.
- [x] `create_github_pending_link_token(user_id, github_id) -> str`: a JWT with
      `{"type": "github_pending_link", "userId": str(user_id), "githubId": github_id}` plus the usual
      `aud`/`iat`/`exp`.
- [x] New setting `JWT_GITHUB_PENDING_LINK_TOKEN_EXPIRY_SECONDS = 10 * 60` (a constant, like the other
      token expiries).
- [x] `decode_token(..., expected_type="github_pending_link")` also requires `githubId` and checks that it
      is an `int` (`InvalidToken` otherwise; `bool` is rejected too). `userId` is parsed as a UUID like in
      the other types. The required and UUID claims per type now live in `UUID_CLAIMS` / `INT_CLAIMS`.
- [x] Token tests (from step 5): round-trip; type enforced both ways; missing or non-int `githubId`;
      malformed `userId`.
- Why a signed token and not a DB row: the client can't swap the GitHub id or the target account, and no
  table or cleanup is needed. It can be redeemed again within 10 minutes, but only with the password, and
  after the first success it fails because the account already has a `github_id`.

### 2. User service `link_github`

File: `user/services.py`

- [x] `link_github(user, github_id, session)`: set `user.github_id` and commit. On `IntegrityError`
      (concurrent link or registration of the same GitHub id), roll back and raise `UserAlreadyExists`.
      No `repo` parameter: it doesn't query anything.
- [x] Update the `register_user_by_github` docstring ("never merged by email" → "linked only after the
      account's password is confirmed").
- [x] Tests: sets `github_id`; a unique violation on commit → `UserAlreadyExists` + rollback.

### 3. `POST /auth/github` returns `ACCOUNT_EXISTS` with the pending link token

Files: `auth/services.py`, `auth/exceptions.py`, `auth/router.py`, `auth/schemas.py`

- [x] New exceptions:
  - `GithubLinkRequired(email, pending_link_token)`
  - `GithubEmailTaken`
- [x] `User.can_link_github` property (`github_id is None and password is not None`), following the
      "fat models" guideline in [AGENTS.md](../AGENTS.md).
- [x] In `login_with_github`, when no user has this `github_id`, look up the GitHub email before
      registering:
  - The email belongs to a user that `can_link_github` → raise `GithubLinkRequired` with
    `create_github_pending_link_token(user.id, github_user.id)`.
  - The email belongs to any other user (one with a **different** `github_id`, or with no password, which
    can't happen today) → raise `GithubEmailTaken`.
  - No user has the email → register as today.
- [x] Keep the existing fallback that handles concurrent first logins with the same GitHub account.
- [x] Router responses. The body is wrapped in `detail`, like the API's other errors:
  - `GithubLinkRequired` → 409
    `{"detail": {"code": "ACCOUNT_EXISTS", "message": "...", "email": "...", "pending_link_token": "..."}}`
  - `GithubEmailTaken`, or `UserAlreadyExists` from a concurrent registration → 409
    `{"detail": {"code": "EMAIL_TAKEN", "message": "..."}}`
  - Schemas `GithubConflict` / `GithubConflictResponse`, declared in `responses=` so they show in the
    OpenAPI docs.
- [x] Tests: `ACCOUNT_EXISTS` with a valid token and no user created; `EMAIL_TAKEN`; a GitHub user without
      an email still doesn't take one already used; `can_link_github`; the router's 409 bodies.
- The current frontend checks only for status 409, so it keeps showing its "email taken" message until it
  handles `ACCOUNT_EXISTS`.

### 4. `POST /auth/github/link-pending`

Files: `auth/router.py`, `auth/services.py`, `auth/schemas.py`

- [x] Unauthenticated. Body: `GithubPendingLinkRequest { pending_link_token, password }` (password max
      `PASSWORD_MAX_LENGTH`).
- [x] Service `link_github_with_password(...)`:
  1. Decode the token (`expected_type="github_pending_link"`). Invalid or expired → 401.
  2. Load the user by `userId`. Missing user, no password, or wrong password → 401 with the same message as
     `/auth/login` ("Incorrect email or password"). Check the password through a helper shared with
     `login_with_password` (e.g. `check_password(user, password)` raising `InvalidCredentials`), so the
     future rate limiting covers both endpoints.
  3. Check the state again: the user still has no `github_id`, and no other user has `githubId`. Otherwise
     → 409. `uq_user_github_id` catches races through `link_github`.
  4. `link_github(user, githubId, session)`, then `start_session(...)` → `TokenPair`.
- [x] Log `User with id=%s linked GitHub id=%s` (audit trail).
- Design choice: the password goes straight into this endpoint. The alternative (log in through
  `/auth/login` first, then call this with a Bearer token and no password) needs two calls and an
  "is the login recent enough" check.

### 5. Tests

File: `tests/test_auth.py` (reuse the `login_github` fixture and `_github_client`)

- [x] Pending link token: round-trip; an access or refresh token is rejected as `github_pending_link`, and
      the reverse; a token without `githubId`, or with a non-int `githubId`, is rejected (done in step 1).
- [x] `/auth/github` with the email of a password account → `GithubLinkRequired`; no user created; the token
      carries that user's id and the GitHub id (replaces
      `test_github_login_does_not_take_email_of_another_account`) (done in step 3).
- [x] `/auth/github` with an email of an account linked to a different GitHub id → `GithubEmailTaken`
      (done in step 3).
- [x] `link-pending` success: `github_id` is set, a `TokenPair` is returned, and a later `login_with_github`
      resolves to the same user through `github_id`.
- [x] `link-pending` with a wrong password → 401; `github_id` stays unset.
- [x] `link-pending` with an expired or tampered token → 401.
- [x] `link-pending` when the account got a `github_id` in the meantime, or the GitHub id now belongs to
      another account → 409.
- [x] Password login still works after linking.

### 6. Migrations

None. `user.github_id` and `uq_user_github_id` already exist.

## Security notes

- **An attacker's GitHub account shows a victim's email:** the attacker gets a pending token but can't link
  without the victim's password.
- **An attacker pre-registered the victim's email with a password, and the victim then uses GitHub:** the
  victim is asked for a password they don't know, so nothing is linked into the attacker's account. The
  victim's real fix is a password reset (out of scope).
- **A leaked pending token** is useless without the password, and it expires in 10 minutes.
- **The `ACCOUNT_EXISTS` response shows that the email has an account.** This adds no new information,
  because `/auth/email-available` already reveals it.
- **`link-pending` checks passwords**, so it can be used to guess them just like `/auth/login`. Neither
  endpoint is rate limited yet (see resolved question 2).

## Resolved questions

1. **Separate `auth_identity` table: dropped.** The design discussion recommended
   `AuthIdentity(user_id, provider, provider_user_id, password_hash)` with
   `UNIQUE(provider, provider_user_id)`. With two login methods, the current `github_id` and `password`
   columns plus their unique constraints give the same guarantees, so the schema stays as it is.
2. **Rate limiting: deferred to a separate plan and PR.** It protects `/auth/login` as much as
   `/auth/github/link-pending`. This plan doesn't wait for it, but `link-pending` must check the password
   through the same helper as `/auth/login` (step 4), so the future limit covers both endpoints. Notes for
   that plan:
   - Per-account limit: failed checks per normalized email, stored in Postgres, shared by both endpoints;
     429 + `Retry-After` even for a correct password; temporary, never a permanent lock; unknown emails
     counted the same way.
   - Per-IP limit: the API is reachable only from the Next server, so Next must forward the client IP
     (from Caddy's `X-Forwarded-For`).
   - Run scrypt in a thread so it doesn't block the event loop.

## Out of scope

- Frontend:
  - [api/oauth/github/route.ts](../../web/src/app/api/oauth/github/route.ts) handles the
    `ACCOUNT_EXISTS` 409: it keeps `pending_link_token` in a short-lived httpOnly cookie and redirects to
    something like `/login?link=github`.
  - That page shows the email (read-only) and a password field, and calls `link-pending`.
- Connecting GitHub from account settings (dropped). Consequence: a GitHub account whose primary email
  differs from the account email can't be linked. GitHub login with it creates a separate account, as today.
- OAuth `state` checking. It lives in the frontend route, since the backend only receives `code`.
- The reverse case: adding a password to an account created through GitHub (a separate plan).
- Disconnecting GitHub. It would need a "can't remove your last login method" rule.
- Email verification for password signups. Once it exists, automatic linking of two verified emails could
  be reconsidered.
