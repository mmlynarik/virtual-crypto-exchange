# Virtual Crypto Exchange

A full-stack virtual crypto exchange: users sign up with an email and password or with GitHub, and the app
keeps crypto market data from [CoinGecko](https://www.coingecko.com/) in its own database.

Live at [mmlynarik.com](https://mmlynarik.com).

## Repository

| Path | What it is |
|---|---|
| [api/](api/) | Backend: FastAPI on Python 3.14, async SQLAlchemy, PostgreSQL, Alembic migrations. See [api/README.md](api/README.md). |
| [web/](web/) | Frontend: Next.js 15, React 19, Tailwind CSS 4. See [web/README.md](web/README.md). |
| [docker-compose-dev.yaml](docker-compose-dev.yaml) | Local stack: `db`, `api`, `web` |
| [docker-compose-prod.yaml](docker-compose-prod.yaml) | Server stack: `db`, `api`, `web`, `caddy` (HTTPS reverse proxy), `watchtower` (image auto-update) |
| [justfile](justfile) | Shortcuts for running the stacks and migrations (`just` lists them) |
| [.github/workflows/](.github/workflows/) | Build the production images and push them to Docker Hub |

How the parts fit together:

- The browser talks only to `web`. `web` calls the API at `BACKEND_API_URL` from the server side and keeps
  the user's access and refresh tokens in httpOnly cookies.
- The API owns all auth (passwords, GitHub OAuth, JWTs, refresh token rotation) and stores users,
  sessions and coins in PostgreSQL.
- The API applies database migrations on every container start (`vce-migrate`).

### Features

- Email and password sign-up and login, with client-side and server-side form validation
- GitHub login, and linking GitHub to an existing password account after the password is confirmed
- JWT access tokens with rotating refresh tokens; reusing a refresh token revokes the session
- Coin data fetched from CoinGecko and stored in the database

## Prerequisites

| Tool | Needed for |
|---|---|
| [Docker](https://docs.docker.com/get-docker/) with Compose v2 | Running the dev and prod stacks |
| [just](https://github.com/casey/just) | The commands in the [justfile](justfile) |
| [uv](https://docs.astral.sh/uv/) | Backend environment, tests, migrations, linting. It installs Python 3.14 if you don't have it. |
| [Node.js](https://nodejs.org/) 22.12 or newer, with npm | Frontend environment and tests |
| `openssl` | Generating the JWT secret |
| A [GitHub OAuth app](https://github.com/settings/developers) | GitHub login. Its client secret goes into the env file. |

Development happens on Linux (WSL works).

## Development environment

1. Clone the repository:

   ```sh
   git clone git@github.com:mmlynarik/virtual-crypto-exchange.git
   cd virtual-crypto-exchange
   ```

2. Create the secrets file for the dev stack. It is git-ignored.

   ```sh
   cp .env.example .env.dev
   ```

   Fill in:
   - `JWT_SECRET_KEY`: generate it with `openssl rand -base64 32`.
   - `GITHUB_CLIENT_SECRET`: the secret of the dev GitHub OAuth app.

   The dev OAuth app's client ID is set in
   [docker-compose-dev.yaml](docker-compose-dev.yaml). If you use your own OAuth app, change
   `GITHUB_CLIENT_ID` there and set the app's callback URL to `http://localhost:3000/api/oauth/github`.

3. Install the backend environment and the git hooks. The hooks run ruff, black, mypy and isort on
   `api/`.

   ```sh
   cd api
   uv sync
   uv run pre-commit install
   cd ..
   ```

4. Install the frontend dependencies, for editor support and running tests outside Docker:

   ```sh
   cd web
   npm install
   cd ..
   ```

5. Optional, for running migrations from the host with `just migrate` / `just checkmig`: create
   `api/.env` with the connection to the dev database, which is published on `localhost:5433`:

   ```sh
   BACKEND_DB_HOST=localhost:5433
   BACKEND_DB_NAME=postgres
   BACKEND_DB_USER=postgres
   BACKEND_DB_PASSWORD=postgres
   ```

## Running the app

### Development

Prerequisites: Docker, just, and `.env.dev` from step 2 above.

```sh
just rundev            # start db, api and web in the foreground
just rundev --build    # rebuild the images first, after changing dependencies
```

| Service | URL |
|---|---|
| Web app | http://localhost:3000 |
| API | http://localhost:8000 |
| API docs (Swagger UI) | http://localhost:8000/docs |
| PostgreSQL | `localhost:5433`, user and password `postgres` |

- `api/vce` is mounted into the `api` container, so backend changes reload without a rebuild.
- The `web` container runs a production build of Next.js. Rebuild it (`just rundev --build`) to see
  frontend changes.
- For live reload of the frontend, run it outside Docker with `npm run dev` in `web/`. It needs
  `web/.env` with `BACKEND_API_URL=http://localhost:8000/api`, `GITHUB_CLIENT_ID` and
  `GITHUB_REDIRECT_URL=http://localhost:3000/api/oauth/github`.

### Tests and checks

Prerequisites: steps 3 and 4 of the development environment. The tests need no database.

```sh
cd api && uv run pytest                          # backend tests
cd api && uv run pre-commit run --all-files      # lint, format and type check: the hooks run on commit
cd web && npm test                               # frontend tests (vitest)
```

### Production

Prerequisites on the server: Docker, just, a clone of this repository, DNS for the domains in the
[Caddyfile](Caddyfile) pointing at the server, and ports 80 and 443 open.

1. Create `.env.prod` from [.env.example](.env.example) and fill in `JWT_SECRET_KEY`,
   `GITHUB_CLIENT_SECRET` (of the prod OAuth app) and `BACKEND_DB_PASSWORD`.
2. Start the stack:

   ```sh
   just runprod -d
   ```

The stack doesn't build anything: it pulls `miromlynarik/vce-api:prod` and `miromlynarik/vce-web:prod`
from Docker Hub. GitHub Actions builds and pushes these images on every push to `master` that changes
`api/` or `web/`. Watchtower checks for new images every minute and restarts the `api` and `web`
containers when there are. Caddy obtains HTTPS certificates and proxies the domain to `web`.
