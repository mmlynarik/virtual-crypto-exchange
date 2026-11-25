# Plan: link GitHub to an existing account (frontend)

Status: **in progress** (steps 0–2 done), branch `github-account-linking-web`
Scope: web app (`web/`). The backend is done; see
[api/docs/github-account-linking-plan.md](../../api/docs/github-account-linking-plan.md).

## Problem

The backend now answers a GitHub login whose email belongs to a password account with
`409 ACCOUNT_EXISTS` and a pending link token. Redeeming that token with the account's password at
`POST /auth/github/link-pending` links GitHub and logs the user in.

The web app ignores the 409 body. It treats every 409 as "email taken" and shows a message telling the user
to "connect your GitHub account from account settings". That page doesn't exist, and it was dropped from the
plan.

## Backend contract

`POST /auth/github`, 409:

```json
{"detail": {"code": "ACCOUNT_EXISTS", "message": "...", "email": "alice@example.com", "pending_link_token": "<JWT>"}}
{"detail": {"code": "EMAIL_TAKEN", "message": "..."}}
```

`POST /auth/github/link-pending` with `{"pending_link_token": "...", "password": "..."}`:

| Status | Meaning |
| --- | --- |
| 200 | `TokenPair`: linked and logged in |
| 401 | Wrong password, or an invalid or expired token (same status, so the web app checks expiry itself) |
| 409 | The account or the GitHub account got linked in the meantime |
| 422 | Password longer than the backend's maximum |

The pending link token is a JWT, `{"type": "github_pending_link", "userId", "githubId", "aud", "iat", "exp"}`,
valid for 10 minutes. The web app can read `exp` without verifying the signature, the same way it reads
access tokens in [jwtSession.ts](../src/lib/auth/jwtSession.ts).

## Target flow

```
GitHub → /api/oauth/github?code=…  (route handler)
   loginWithGithub(code) → link_required { email, pendingLinkToken }
   set httpOnly cookie github_pending_link (path /link-github, expires with the token)
   redirect /link-github

/link-github  (server page)
   no usable cookie → redirect /login?error=github_link_expired
   shows: "An account with alice@example.com already exists. Enter its password to connect GitHub."
          [email, read-only] [password] [Connect GitHub and log in]  [Cancel]

Submit → linkGithubAction (server action)
   token expired             → clear cookie, redirect /login?error=github_link_expired
   200                       → clear cookie, set session cookies, redirect /home
   401                       → form error "Incorrect password" (the user can try again)
   409                       → clear cookie, redirect /login?error=github_link_conflict
Cancel → cancelGithubLink: clear cookie, redirect /login
```

The pending link token never reaches client JavaScript. It lives only in an httpOnly cookie, which the server
page and the server action read.

## Decisions

- **A separate page, `/link-github`, not a mode of the login form.** It has its own purpose, message and
  submit action. The login form stays as it is.
- **The token and email are kept in one httpOnly cookie**, not in the URL (no personal data in URLs) and not
  in client state. The cookie's `path` is `/link-github`, so the browser sends it only to that page and its
  server actions, and it expires together with the token.
- **No backend change for "expired" versus "wrong password".** Both are 401 from the backend. The web app
  checks the token's `exp` before calling the backend, so an expired token gets its own message. A 401 for a
  token that was still valid then means a wrong password.
- **"Email taken" message changes.** With no settings page, the old advice is wrong. `EMAIL_TAKEN` now means
  the email belongs to an account linked to a different GitHub account, and the message says that.

## Steps

### 0. Test setup (Vitest)

The web app has no tests yet. Tests are written first for each step below, so this step comes first.

- [x] Add `vitest` as a dev dependency and a `"test": "vitest run"` script.
- [x] `vitest.config.mts` (`.mts` because the package isn't `"type": "module"`): the `@/` path alias, and
      an alias that maps `server-only` to an empty module (the real package throws outside a Next.js
      server build).
- [x] Scope: unit tests for `lib/` modules (`backend.ts` with a mocked `fetch`, the cookie helpers with a
      mocked `next/headers`, the server actions with `redirect` mocked). Pages and components are checked
      by hand in step 8.
- [x] First test: `lib/auth/jwtSession.test.ts` (`isAccessTokenUsable`), which also proves the `@/` and
      `server-only` aliases. Run with `npm test`.

### 1. Parse the `/auth/github` 409 body

File: [lib/auth/backend.ts](../src/lib/auth/backend.ts)

- [x] Zod schema for the 409 body (`detail.code`, `message`, optional `email` and `pending_link_token`).
- [x] New `GithubLoginResult` variant
      `{ok: false; reason: "link_required"; email: string; pendingLinkToken: string}`.
- [x] `ACCOUNT_EXISTS` with an email and a token → `link_required`. `EMAIL_TAKEN`, or a 409 body that doesn't
      parse → `email_taken`, as today.
- [x] Tests: each 409 shape (including the old plain-string body and a non-JSON body); 401 → `rejected`;
      200 → tokens; 500 → `BackendError`. `BACKEND_API_URL` for tests is set in the Vitest config.
- Until step 4, the callback route sends `link_required` to the generic "GitHub login failed" message.

### 2. Call `/auth/github/link-pending`

File: [lib/auth/backend.ts](../src/lib/auth/backend.ts)

- [x] `linkGithubPending(pendingLinkToken, password)` returning
      `{ok: true; tokens} | {ok: false; reason: "wrong_password" | "already_linked"}`.
- [x] 401 → `wrong_password`; 422 → `wrong_password` too (only a password longer than the backend's maximum
      gets 422, and no account can have one); 409 → `already_linked`; anything else not OK → `BackendError`.
- [x] Tests: each status, and the request's path and body.

### 3. Pending link cookie

New file: `lib/auth/githubLink.ts` (`server-only`). Token claims schema in
[lib/schemas/jwt.ts](../src/lib/schemas/jwt.ts).

- [ ] `githubPendingLinkTokenSchema`: `type: "github_pending_link"`, `userId`, `githubId`, `aud`, `exp`.
- [ ] `setPendingGithubLink(email, token)`: one httpOnly, `sameSite: "lax"` cookie `github_pending_link`
      holding `{email, token}` as JSON, `path: "/link-github"`, `expires` = the token's `exp`.
- [ ] `getPendingGithubLink()`: `{email, token}`, or `null` when the cookie is missing, malformed, or holds
      a token that is expired or about to expire (a short leeway, like `EXPIRY_LEEWAY_SECONDS`).
- [ ] `clearPendingGithubLink()`.
- [ ] Tests: round-trip; missing, malformed and expired cookies → `null`; the cookie options (httpOnly, path,
      expires).

### 4. GitHub callback route

File: [app/api/oauth/github/route.ts](../src/app/api/oauth/github/route.ts)

- [ ] On `link_required`: `setPendingGithubLink(email, pendingLinkToken)`, then redirect to `/link-github`.
- [ ] The other results are unchanged.

### 5. Server actions

New file: `lib/actions/githubLink.ts`. Password schema in `lib/schemas/githubLink.ts`.

- [ ] `linkGithubAction(prevState, formData)`:
  1. Validate the password with zod (required).
  2. `getPendingGithubLink()` returns `null` → redirect `/login?error=github_link_expired`.
  3. `linkGithubPending(...)`:
     - OK → `clearPendingGithubLink()`, `setSessionCookies(tokens)`, redirect `/home`.
     - `wrong_password` → return the form error "Incorrect password" (the cookie stays, so the user can
       retry).
     - `already_linked` → `clearPendingGithubLink()`, redirect `/login?error=github_link_conflict`.
- [ ] `cancelGithubLink()`: `clearPendingGithubLink()`, redirect `/login`.
- [ ] Tests: each branch, with the backend client, cookies and `redirect` mocked.

### 6. `/link-github` page

New files: `app/(auth)/link-github/page.tsx`, `components/LinkGithubForm.tsx`.
Edit: [middleware.ts](../src/middleware.ts).

- [ ] Add `/link-github` to `publicRoutes`. A logged-in user is still sent to `/home`, as on `/login`.
- [ ] Server page: `getPendingGithubLink()`; `null` → redirect `/login?error=github_link_expired`.
      Otherwise render `LinkGithubForm` with the email only (never the token).
- [ ] `LinkGithubForm` (client), styled like `LoginForm` (`Card`, `Form`, `FormButton`, the same error box):
  - Title "Connect GitHub".
  - Text: "An account with **{email}** already exists. Enter its password to connect your GitHub account.
    You can then log in with either."
  - The email as a read-only input (also helps password managers fill the right entry), then the password
    with `autoFocus`.
  - "Connect GitHub and log in" (pending: "Connecting"), and a "Cancel" button calling `cancelGithubLink`.
  - The action's error shown in the dismissible error box.

### 7. Login page messages

File: [app/(auth)/login/page.tsx](../src/app/(auth)/login/page.tsx)

- [ ] `github_email_taken`: "An account with your GitHub email already exists and is connected to a
      different GitHub account." (The settings advice goes.)
- [ ] New `github_link_expired`: "Connecting GitHub took too long. Log in with GitHub again to retry."
- [ ] New `github_link_conflict`: "This account or this GitHub account is already connected. Try logging in
      with GitHub or your password."

### 8. Manual check (dev stack, `just rundev`)

- [ ] Sign up with a password using the email that is primary and verified on your GitHub account, then log
      out.
- [ ] "Log in with GitHub" → `/link-github` showing that email.
- [ ] A wrong password → "Incorrect password", still on the page; the right one → `/home`.
- [ ] Log out, then "Log in with GitHub" → straight to `/home`. Password login still works.
- [ ] Cancel → `/login`, and opening `/link-github` again redirects with the expired message.
- [ ] Waiting more than 10 minutes before submitting → the expired message on `/login`.
- [ ] Browser dev tools: the `github_pending_link` cookie is httpOnly, scoped to `/link-github`, and gone
      after linking or cancelling.

## Resolved questions

1. **Vitest (step 0): added.** The web app gets its first test setup, so each step starts with its tests.
2. **OAuth `state`: postponed to a later branch.** `GITHUB_AUTHORIZE_URL` sends no `state`, and the callback
   doesn't check one. An attacker can therefore make a victim's browser finish a GitHub login with the
   attacker's code, so the victim is silently logged into the attacker's account ("login CSRF"). This is an
   existing gap, not caused by linking: a pending link needs the target account's password, so it can't be
   abused this way. Fix later: a random `state` in a short-lived httpOnly cookie, checked in the callback
   route.

## Out of scope

- OAuth `state` (resolved question 2: a later branch).
- Rate limiting of password attempts (deferred on the backend).
- Signing up with a password when the email belongs to a GitHub account (unchanged: "Email is already in
  use").
- Adding a password to an account created through GitHub.
