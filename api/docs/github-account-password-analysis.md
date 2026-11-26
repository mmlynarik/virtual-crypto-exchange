# Analysis: add a password to an existing GitHub account

Status: **analysis**. No option chosen yet, nothing implemented.
Reverse of [github-account-linking-plan.md](github-account-linking-plan.md), which links GitHub to an existing
password account.

## Problem

A user signs up with "Continue with GitHub". Their account has `github_id` set and `password IS NULL`. Later
they want to log in with email + password as well.

Today they can't:

- `POST /auth/register` with that email answers `409`, and the signup form shows "Email is already in use".
- `POST /auth/login` with that email answers `401`, because `User.check_password` raises `WrongPassword` when
  there is no password.
- No settings page exists to add a password from (`web/src/app/(dashboard)/more/page.tsx` is empty).

## The key asymmetry

In the forward flow, GitHub's **verified** email locates the account, and the account's password proves the
user owns it.

In the reverse flow, the email typed into the signup form is **unverified**. So:

- **A password must never be attached to an account because the email matches.** Anyone could register with a
  victim's email and take over the victim's GitHub-created account.
- **The proof has to be control of the linked GitHub account.** That means an OAuth round trip whose
  `github_user.id == user.github_id`.
- **Email verification is not an alternative.** The backend has no email infrastructure (no SMTP, no
  verification mails).

## What already exists

| Piece | Where |
| --- | --- |
| GitHub id + verified primary email from `/user` and `/user/emails` | [auth/github.py](../vce/auth/github.py) |
| GitHub login looks the user up by `github_id` first | `login_with_github` in [auth/services.py](../vce/auth/services.py) |
| Signed, short-lived proof token pattern (`github_pending_link`, 10 min) | [auth/security.py](../vce/auth/security.py) |
| Redeem endpoint that locks the user and re-checks state | `link_github_with_password` in [auth/services.py](../vce/auth/services.py) |
| Guarded state transition on the domain object | `User.can_link_github` / `User.link_github` in [user/domain.py](../vce/user/domain.py) |
| Pending state held in a cookie on the web side, plus a page to finish it | `web/src/lib/auth/githubLink.ts`, `web/src/app/(auth)/link-github/page.tsx` |
| `?error=` codes shown on `/login` | `web/src/lib/githubLoginErrors.ts` |

## Options

### A. Logged-in "Set password" (settings page)

`POST /auth/password` behind `CurrentUser`, allowed only while `password is None`.

- **A stolen session would become permanent access.** A refresh token lives 24 h. Setting a password turns
  that into a credential that outlives the session. Option A therefore needs a step-up check: the session must
  have been authenticated recently. That means tracking `auth_time` per refresh-token family (a new column,
  carried through rotation) and refusing when it's too old.
- **It doesn't help the user on the signup page.** They have to know to log in with GitHub first and then find
  the setting.
- **It needs a settings UI**, which doesn't exist yet.

### B. Fresh GitHub proof token, the mirror of the forward flow (recommended)

1. The user clicks "Continue with GitHub to set a password". The button is offered as a hint on the signup
   page and later from settings.
2. The OAuth callback reads the intent from `state` and calls `POST /auth/github/password-setup { code }`. The
   backend exchanges the code and looks the user up by `github_id`:
   - not found → 401 (no account for this GitHub account)
   - `password` already set → 409
   - otherwise → issue a `password_setup` token (`userId`, `githubId`, 10 min). **No session is started
     yet.**
3. A page shows "Set a password for `<stored email>`" and calls
   `POST /auth/password/setup { password_setup_token, password }`. That call:
   - locks the user
   - re-checks that `github_id == githubId` and that `password is None`
   - sets the password, starts a session, and commits

```
User                                                Backend
────                                                ───────
"Continue with GitHub to set a password"
  → GitHub → back with ?code&state (intent=set_password)
  ────────────────────────────────────────────────▶ POST /auth/github/password-setup { code }
                                                     code exchange → githubId 12345678
                                                     user U has github_id 12345678, no password
                    ◀──────────────────────────── 200 { email, password_setup_token (U, 12345678, 10 min) }
  "Set a password for alice@example.com"
  ────────────────────────────────────────────────▶ POST /auth/password/setup
                                                     { password_setup_token, password }
                                                     lock U, re-check, set password
                    ◀──────────────────────────── 200 TokenPair (logged in)
```

Why B is better:

- **The GitHub proof is always fresh**, so no `auth_time` tracking is needed.
- **It works logged out** (from signup) **and logged in** (from settings).
- **It reuses the shape that already exists**: a signed pending token, a redeem endpoint, cookie-held pending
  state on the web side, and the same error mapping.
- **A stolen VCE session can't set a password.** That also needs the victim's GitHub session.

**Caveat:** GitHub approves an already-authorized app without prompting. So "fresh proof" means control of the
browser's GitHub session, not a re-entered GitHub password. That's still much stronger than a stolen VCE token,
and it's the same trust that GitHub login already relies on.

## What option B needs

### Prerequisite: OAuth `state`

`GITHUB_AUTHORIZE_URL` in `web/src/config.ts` sends no `state` parameter, and the callback
(`web/src/app/api/oauth/github/route.ts`) doesn't check one. That is a **login-CSRF hole today**: an attacker
can send a victim a callback URL carrying the attacker's `code`, and the victim gets logged into the attacker's
account.

Option B also needs `state` to carry the intent (`login` vs `set_password`).

Fix: generate a random nonce, store it with the intent in an httpOnly cookie, send the nonce as `state`, and
compare the two in the callback. This is worth doing regardless of this feature, and it should come first.

### Backend

- **Domain** ([user/domain.py](../vce/user/domain.py)): `User.can_set_password` (`password is None`) and
  `User.set_password(password)`, which raises `PasswordAlreadySet`. Mirrors `can_link_github` /
  `link_github`.
- **Tokens** ([auth/domain.py](../vce/auth/domain.py), [auth/security.py](../vce/auth/security.py)): add
  `"password_setup"` to `TokenType`, with UUID claim `userId` and int claim `githubId`. Add
  `create_password_setup_token` and a `JWT_PASSWORD_SETUP_TOKEN_EXPIRY_SECONDS` setting.
- **Services** ([auth/services.py](../vce/auth/services.py)):
  - `start_password_setup(code, uow, client)`: code exchange, look up by `github_id`, issue the token.
  - `set_password_with_github(token, password, uow)`: lock the row before re-checking, so concurrent redeems
    serialize and the second one gets 409.
- **Schemas** ([auth/schemas.py](../vce/auth/schemas.py)): pull out a `NewPassword` annotated type (the
  min/max length rules from `EmailRegisterCredentials`), so signup and setup validate passwords identically.
- **Router** ([auth/router.py](../vce/auth/router.py)): two endpoints, with errors mapped like
  `/auth/github/link-pending`: invalid or expired token → 401, already set → 409.
- **Tests**: unit tests for the domain guard, service tests for the happy path, wrong GitHub id, password
  already set, expired or wrong-type token, and a concurrent double redeem.

### Web

- The OAuth callback branches on the intent from `state`.
- A pending-setup cookie and a `/set-password` page, modelled on `link-github`.
- A hint on the signup form when the email is taken, which starts the GitHub flow with `intent=set_password`.
- New `?error=` codes: no account for this GitHub account, password already set, setup expired.

## Open decisions

1. **Signup hint wording.** A specific message ("This email signed up with GitHub") reveals how any email
   signs in. `/auth/email-available` already reveals that an email exists, but not how. **Proposal:** one
   generic message for every taken email: "Email already in use. Signed up with GitHub? Continue with GitHub to
   add a password."
2. **Which email the password logs in with.** It should be the **stored** `user.email`, not the current GitHub
   primary email. The stored one doesn't sync with GitHub and may be stale. Updating it would need its own
   uniqueness and conflict handling. **Proposal:** keep the stored email and show it clearly on the setup page.
3. **Other sessions.** Should setting the password revoke the user's other refresh-token families? Adding a
   credential is less sensitive than changing one. **Proposal:** don't revoke. It's a one-line change if
   wanted.

## Out of scope

- Changing a password. It needs the current password and is a separate feature.
- Unlinking GitHub.
- The invariant that every user keeps at least one credential. It only matters once unlinking or password
  removal exists.
